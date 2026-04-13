import logging
import os
import datetime
import json
import threading
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import openai
from dotenv import load_dotenv

from utils.timezone_utils import (
    build_time_context,
    get_configured_timezone_name,
    today_in_configured_timezone,
    today_iso_in_configured_timezone,
)

load_dotenv()

_logger = logging.getLogger(__name__)

DEFAULT_LLM_MODEL = "gpt-4.1-mini"
DEFAULT_AUDIO_TRANSCRIBE_MODEL = "gpt-4o-mini-transcribe"
PROMPT_FILE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "openai_prompt.txt")
)
PROMPT_TEMPLATE_FILE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "openai_prompt_template.txt")
)
DEFAULT_PROMPT = (
    "Você é um assistente de produtividade e deve responder em português para mensagem do Telegram."
    "\nObjetivo: priorizar tarefas, explicar rapidamente os motivos e sugerir próximo passo."
    "\n\nFormato obrigatório da resposta (Markdown):"
    "\n## Prioridades de hoje"
    "\n- **[Alta] Nome da tarefa** — motivo curto + tempo estimado"
    "\n- **[Média] Nome da tarefa** — motivo curto + tempo estimado"
    "\n- **[Baixa] Nome da tarefa** — motivo curto + tempo estimado"
    "\n\n## Próximo passo recomendado"
    "\nUma frase objetiva com a melhor ação agora."
    "\n\nRegras:"
    "\n- Não responder em JSON."
    "\n- Seja breve e direto."
    "\n- Se não houver tarefa, escreva exatamente: \"Sem tarefas para priorizar hoje.\""
    "\n- Considere o campo Tags (ex.: TAKES TIME, FAST, FUP, CRITICAL) para ajustar a priorização por esforço/urgência."
    "\n- Use o campo projeto para equilibrar prioridades entre contextos (ex.: Pessoal, Draiven, Monks)."
    "\n- Tarefas com mais de 3 dias de atraso são automaticamente CRÍTICAS, independente de outros fatores."
    "\n- Se a lista tiver mais de 12 tarefas, agrupe por projeto e destaque as 2-3 mais urgentes de cada um."
    "\n- Na lista final, para cada tarefa, mostre explicitamente o projeto e uma label de prazo: [ATRASADA] ou [NO PRAZO]."
    "\n\nTarefas:"
)
TASK_PARSER_PROMPT = (
    "Você recebe uma frase para criar uma tarefa e deve retornar somente JSON válido."
    "\nExtraia os campos: task_name, project, due_date, tags."
    "\nRegras:"
    "\n- task_name deve ter a primeira letra maiúscula e as demais em caixa normal (não ALL CAPS)."
    "\n- due_date deve estar em formato YYYY-MM-DD."
    "\n- tags deve ser uma lista de strings em UPPERCASE."
    "\n- tags deve representar tipo/complexidade/contexto da tarefa (ex.: FAST, TAKES TIME, FOLLOWUP, DEEP WORK, ADMIN, CRITICAL)."
    "\n- tags NÃO deve representar data/período/horário (ex.: amanhã, hoje, manhã, tarde, noite, segunda, urgente amanhã)."
    "\n- Se a frase contiver palavras como \"urgente\", \"urgentemente\" ou \"crítico\", adicione a tag CRITICAL."
    "\n- Se data não for informada, use a data de hoje."
    "\n- Se projeto não for informado, use \"Pessoal\"."
    "\n- Não inclua texto fora do JSON."
    "\nExemplo:"
    "\n{\"task_name\":\"Revisar proposta comercial\",\"project\":\"Trabalho\",\"due_date\":\"2026-03-01\",\"tags\":[\"DEEP WORK\",\"FOLLOWUP\"]}"
)
EVENT_PARSER_PROMPT = (
    "Você recebe uma frase para criar um evento no Google Calendar e deve retornar somente JSON válido."
    "\nExtraia os campos: summary, start_datetime, end_datetime, description, location, timezone."
    "\nRegras:"
    "\n- Corrija erros gramaticais e normalize o texto do usuário antes de preencher summary/description."
    "\n- O summary deve ser curto, claro e bem escrito."
    "\n- A description deve ser reescrita com gramática correta quando houver texto livre do usuário; use string vazia se não houver."
    "\n- start_datetime e end_datetime devem estar em formato YYYY-MM-DDTHH:MM."
    "\n- Se o usuário mencionar duração (ex.: \"reunião de 1h\", \"30 minutos\"), calcule end_datetime a partir de start_datetime."
    "\n- Se end_datetime não puder ser determinado, assuma duração padrão de 1 hora."
    "\n- location deve conter o local do evento (endereço, link, sala); use string vazia se não informado."
    "\n- timezone deve ser um timezone IANA (ex.: America/Sao_Paulo)."
    "\n- Se timezone não for informado, use \"America/Sao_Paulo\"."
    "\n- Não inclua texto fora do JSON."
    "\nExemplo:"
    "\n{\"summary\":\"Reunião de kickoff\",\"start_datetime\":\"2026-03-03T10:00\",\"end_datetime\":\"2026-03-03T11:00\","
    "\"description\":\"Kickoff do projeto X com o cliente.\",\"location\":\"Sala de reuniões 2\",\"timezone\":\"America/Sao_Paulo\"}"
)
NOTE_PARSER_PROMPT = (
    "Você recebe uma frase para criar uma anotação e deve retornar somente JSON válido."
    "\nExtraia os campos: note_name, tag, observations, url."
    "\nRegras:"
    "\n- note_name deve ser curto, claro e com a primeira letra maiúscula."
    "\n- tag deve ser em UPPERCASE, coerente com o tema principal e uma única palavra ou sigla."
    "\n- Vocabulário preferido de tags: IDEA, REFERENCE, MEETING, LEARNING, FINANCE, HEALTH, PERSONAL, WORK, TASK, TECH."
    "\n- observations deve conter o conteúdo principal da anotação, bem escrito e corrigido gramaticalmente."
    "\n- url deve conter link válido (http/https) quando houver; caso contrário, string vazia."
    "\n- Não inclua texto fora do JSON."
    "\nExemplo:"
    "\n{\"note_name\":\"Ideia para onboarding\",\"tag\":\"IDEA\",\"observations\":\"Criar checklist inicial para novos clientes.\",\"url\":\"\"}"
)
NOTE_METADATA_PROMPT = (
    "Você recebe o conteúdo Markdown de uma anotação pessoal e deve retornar somente JSON válido."
    "\nGere dois campos: title e tags."
    "\nRegras:"
    "\n- title: um título curto e descritivo (máx. 60 caracteres) que resuma o conteúdo."
    "\n- tags: lista de 1 a 5 tags relevantes em minúsculas. Tags são palavras-chave curtas (1-2 palavras)."
    "\n- Use o mesmo idioma do conteúdo para título e tags."
    "\n- Se o conteúdo estiver vazio ou for muito curto, use title \"Nova anotação\" e tags []."
    "\n- Não inclua texto fora do JSON."
    "\nExemplo:"
    "\n{\"title\":\"Planejamento sprint Q2\",\"tags\":[\"trabalho\",\"sprint\",\"planejamento\"]}"
)
CALENDAR_SUMMARY_PROMPT = (
    "Você é um assistente pessoal e deve resumir eventos da agenda da semana em português."
    "\nFormato obrigatório em Markdown:"
    "\n## Agenda da semana"
    "\n- **DD/MM HH:MM** — Evento (contexto curto) [local se disponível]"
    "\n## Destaques"
    "\n- Bullet por cada ponto relevante: conflito de horário, bloco longo, janela livre, evento em <24h."
    "\nRegras:"
    "\n- Seja breve e útil."
    "\n- Eventos que ocorrem em menos de 24 horas a partir de agora: prefixar com ⚡."
    "\n- Se dois eventos se sobrepõem no horário, sinalize com ⚠️ conflito."
    "\n- Eventos recorrentes: adicionar `(recorrente)` ao final da linha."
    "\n- Ao listar eventos, não inclua links automaticamente; mostre apenas nome, dia e horário."
    "\n- Só inclua links ou detalhes extras de um evento quando o usuário pedir explicitamente."
    "\n- Se não houver eventos, responda exatamente: \"Sem eventos na agenda para os próximos 7 dias.\""
)
DAY_SUMMARY_PROMPT = (
    "Você é um assistente pessoal e deve gerar um resumo do dia em português."
    "\nFormato obrigatório em Markdown:"
    "\n## Resumo do dia"
    "\n### Tarefas de hoje"
    "\n- **[ATRASADA] ou [NO PRAZO]** — Tarefa (Projeto) [Tags]"
    "\n### Agenda de hoje"
    "\n- **HH:MM** — Evento (local opcional)"
    "\n### Foco recomendado"
    "\n- Mencione explicitamente a tarefa mais importante do dia."
    "\n- Até 2 bullets adicionais com próximos passos concretos."
    "\nRegras:"
    "\n- Seja objetivo, claro e organizado."
    "\n- Não responder em JSON."
    "\n- Tarefas com prazo anterior a hoje devem ser marcadas [ATRASADA]; demais, [NO PRAZO]."
    "\n- Se não houver tarefas e nem eventos hoje, responda exatamente:"
    "\n\"## Resumo do dia\\n\\nSem tarefas e sem eventos para hoje.\""
)


class OpenAICallError(Exception):
    """Raised when an OpenAI API call fails after handling."""

    def __init__(self, message: str, original: Exception | None = None):
        super().__init__(message)
        self.original = original


def _safe_openai_call(callable_fn, *, description: str = "OpenAI API call"):
    """Execute *callable_fn* and translate openai exceptions into OpenAICallError."""
    try:
        return callable_fn()
    except openai.APITimeoutError as exc:
        _logger.error("%s timed out: %s", description, exc)
        raise OpenAICallError(
            f"O serviço de IA demorou demais para responder (timeout). Tente novamente.",
            original=exc,
        ) from exc
    except openai.RateLimitError as exc:
        _logger.warning("%s rate-limited: %s", description, exc)
        raise OpenAICallError(
            f"Limite de requisições à IA atingido. Aguarde alguns segundos e tente novamente.",
            original=exc,
        ) from exc
    except openai.AuthenticationError as exc:
        _logger.error("%s authentication failed: %s", description, exc)
        raise OpenAICallError(
            f"Falha de autenticação com o serviço de IA. Verifique a chave OPENAI_KEY.",
            original=exc,
        ) from exc
    except openai.APIConnectionError as exc:
        _logger.error("%s connection error: %s", description, exc)
        raise OpenAICallError(
            f"Não foi possível conectar ao serviço de IA. Verifique a conexão com a internet.",
            original=exc,
        ) from exc
    except openai.APIStatusError as exc:
        _logger.error("%s API status error (HTTP %s): %s", description, exc.status_code, exc)
        raise OpenAICallError(
            f"Erro no serviço de IA (HTTP {exc.status_code}). Tente novamente.",
            original=exc,
        ) from exc


def call_openai_assistant(tasks, project_logger):
    openai_client = _create_openai_client()
    llm_model = _get_llm_model()

    project_logger.info("Calling ChatGPT. This can take a while...")

    completion = _safe_openai_call(
        lambda: openai_client.responses.create(
            model=llm_model,
            input=build_message(tasks),
        ),
        description="call_openai_assistant",
    )

    answer = completion.output_text

    return answer


def parse_add_task_input(user_input, project_logger):
    openai_client = _create_openai_client()
    llm_model = _get_llm_model()

    project_logger.info("Calling LLM to parse add_task input...")
    completion = _safe_openai_call(
        lambda: openai_client.responses.create(
            model=llm_model,
            input=(
                f"{TASK_PARSER_PROMPT}\n\n"
                f"{_build_temporal_prompt_context()}\n\n"
                f"Input do usuário:\n{user_input}"
            ),
        ),
        description="parse_add_task_input",
    )
    return parse_add_task_output(completion.output_text)


def summarize_calendar_events(events, project_logger):
    if not events:
        return "Sem eventos na agenda para os próximos 7 dias."

    openai_client = _create_openai_client()
    llm_model = _get_llm_model()

    project_logger.info("Calling LLM to summarize calendar events...")
    completion = _safe_openai_call(
        lambda: openai_client.responses.create(
            model=llm_model,
            input=build_calendar_events_prompt(events),
        ),
        description="summarize_calendar_events",
    )
    return completion.output_text


def parse_add_event_input(user_input, project_logger):
    openai_client = _create_openai_client()
    llm_model = _get_llm_model()
    default_timezone = _get_default_event_timezone()

    project_logger.info("Calling LLM to parse add_event input...")
    completion = _safe_openai_call(
        lambda: openai_client.responses.create(
            model=llm_model,
            input=(
                f"{EVENT_PARSER_PROMPT}\n"
                f"\nDefault timezone para este usuário: {default_timezone}."
                f"\nSe timezone não for informado pelo usuário, use exatamente {default_timezone}.\n\n"
                f"{_build_temporal_prompt_context()}\n\n"
                f"Input do usuário:\n{user_input}"
            ),
        ),
        description="parse_add_event_input",
    )
    return parse_add_event_output(completion.output_text)


def parse_add_note_input(user_input, project_logger):
    openai_client = _create_openai_client()
    llm_model = _get_llm_model()

    project_logger.info("Calling LLM to parse add_note input...")
    completion = _safe_openai_call(
        lambda: openai_client.responses.create(
            model=llm_model,
            input=f"{NOTE_PARSER_PROMPT}\n\nInput do usuário:\n{user_input}",
        ),
        description="parse_add_note_input",
    )
    return parse_add_note_output(completion.output_text)


def generate_note_metadata(content: str, project_logger) -> dict:
    """Call LLM to generate title and tags from note content. Returns {"title": str, "tags": list[str]}."""
    content_trimmed = (content or "").strip()
    if len(content_trimmed) < 5:
        return {"title": "Nova anotação", "tags": []}

    openai_client = _create_openai_client()
    llm_model = _get_llm_model()

    # Limit content sent to LLM to avoid excessive token usage
    max_chars = 4000
    input_content = content_trimmed[:max_chars]

    project_logger.info("Calling LLM to generate note metadata...")
    completion = _safe_openai_call(
        lambda: openai_client.responses.create(
            model=llm_model,
            input=f"{NOTE_METADATA_PROMPT}\n\nConteúdo da anotação:\n{input_content}",
        ),
        description="generate_note_metadata",
    )

    raw = completion.output_text.strip()
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        data = json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        project_logger.warning("LLM returned invalid JSON for note metadata: %s", raw[:200])
        return {"title": "Nova anotação", "tags": []}

    title = str(data.get("title", "Nova anotação")).strip()[:60] or "Nova anotação"
    raw_tags = data.get("tags", [])
    if not isinstance(raw_tags, list):
        raw_tags = []
    tags = [str(t).strip().lower() for t in raw_tags[:5] if str(t).strip()]

    return {"title": title, "tags": tags}


def estimate_calories(description: str, category: str = "meal", user_weight_kg: float = 75.0, logger=None) -> float | None:
    """Use LLM to estimate calories for a meal or exercise.

    Args:
        description: Human-readable description (e.g. "200g arroz branco" or "corrida 30 min").
        category: "meal" for food calories, "exercise" for calories burned.
        user_weight_kg: Body weight in kg used for exercise calorie estimation (default: 75).
        logger: Optional logger instance.

    Returns:
        Estimated calories as float, or None if estimation fails.
    """
    description = (description or "").strip()
    if not description:
        return None

    openai_client = _create_openai_client()
    llm_model = _get_llm_model()

    weight = max(30.0, min(300.0, float(user_weight_kg or 75.0)))

    if category == "exercise":
        prompt = (
            f"Estime as calorias gastas na seguinte atividade física. "
            f"Considere uma pessoa adulta de {weight:.0f} kg. "
            "Responda APENAS com um número inteiro representando as kcal gastas. "
            "Sem texto adicional, sem unidade — apenas o número.\n\n"
            f"Atividade: {description}"
        )
    else:
        prompt = (
            "Estime as calorias (kcal) da seguinte refeição/alimento na quantidade indicada. "
            "Se a quantidade não for especificada, assuma uma porção padrão típica brasileira. "
            "Considere o método de preparo quando mencionado (grelhado, frito, cozido, etc.). "
            "Responda APENAS com um número inteiro representando as kcal. "
            "Sem texto adicional, sem unidade — apenas o número.\n\n"
            f"Alimento: {description}"
        )

    try:
        completion = _safe_openai_call(
            lambda: openai_client.responses.create(model=llm_model, input=prompt),
            description="estimate_calories",
        )
        raw = completion.output_text.strip().replace(",", ".").replace("kcal", "").strip()
        # Extract first number-like token
        import re as _re
        match = _re.search(r"[\d]+(?:[.,]\d+)?", raw)
        if match:
            value = float(match.group().replace(",", "."))
            if value > 0:
                return round(value, 1)
    except Exception:
        if logger:
            logger.warning("Failed to estimate calories via LLM for: %s", description)
    return None


def estimate_calories_batch(items: list[dict], logger=None) -> list[float | None]:
    """Use a single LLM call to estimate calories for multiple meal items.

    Args:
        items: List of dicts with keys "food" (str) and "quantity" (str).
        logger: Optional logger instance.

    Returns:
        List of estimated calories (float) in the same order as input items.
        Returns 0.0 for any item whose estimation fails.
    """
    if not items:
        return []

    openai_client = _create_openai_client()
    llm_model = _get_llm_model()

    lines = []
    for i, item in enumerate(items, 1):
        food = str(item.get("food", "")).strip()
        quantity = str(item.get("quantity", "")).strip()
        lines.append(f"{i}. {food}, {quantity}" if quantity else f"{i}. {food}")

    prompt = (
        "Estime as calorias (kcal) de cada alimento abaixo na quantidade indicada. "
        "Se a quantidade não for especificada, assuma uma porção padrão típica brasileira. "
        "Considere o método de preparo quando mencionado (grelhado, frito, cozido, etc.). "
        "Responda APENAS com um array JSON de números inteiros, um por linha de entrada, "
        "sem texto adicional, sem unidade, sem markdown. Exemplo para 3 itens: [350, 180, 75]\n\n"
        "Alimentos:\n" + "\n".join(lines)
    )

    try:
        completion = _safe_openai_call(
            lambda: openai_client.responses.create(model=llm_model, input=prompt),
            description="estimate_calories_batch",
        )
        raw = completion.output_text.strip()
        # Extract JSON array from response
        import re as _re
        import json as _json
        match = _re.search(r"\[[\d\s,\.]+\]", raw)
        if match:
            parsed = _json.loads(match.group())
            if isinstance(parsed, list) and len(parsed) == len(items):
                return [round(float(v), 1) if v and float(v) > 0 else 0.0 for v in parsed]
    except Exception:
        if logger:
            logger.warning("Failed to estimate calories in batch via LLM for %d items", len(items))

    return [0.0] * len(items)


_NUTRITIONAL_ANALYSIS_PROMPT = (
    "Você é um nutricionista esportivo. Analise os dados de alimentação e exercícios "
    "dos últimos 7 dias e produza uma análise concisa em português com Markdown.\n\n"
    "Inclua:\n"
    "1. **Resumo calórico** — média diária de consumo, total gasto em exercícios e saldo líquido. "
    "Se a meta calórica do usuário estiver disponível, compare diretamente com ela.\n"
    "2. **Macronutrientes estimados** — proteínas, carboidratos, gorduras (estimativa baseada nos alimentos listados)\n"
    "3. **Pontos positivos** e **Pontos de atenção**\n"
    "4. **Recomendações práticas** — 3 a 5 sugestões objetivas baseadas nos dados reais\n\n"
    "Seja direto e baseado nos dados fornecidos. Máximo 500 palavras."
)


def generate_nutritional_analysis(
    meals: list[dict],
    exercises: list[dict],
    logger=None,
    calorie_goal: int | None = None,
) -> str:
    """Call LLM to produce a 7-day nutritional analysis.

    Args:
        meals: List of meal dicts with keys: food, meal_type, quantity, calories, date.
        exercises: List of exercise dicts with keys: activity, calories, duration_minutes, date.
        logger: Optional logger instance.
        calorie_goal: User's daily calorie goal in kcal; injected into the prompt when provided.

    Returns:
        Markdown-formatted analysis string.
    """
    if not meals and not exercises:
        return "Sem dados de refeições ou exercícios nos últimos 7 dias para analisar."

    # Build data summary for the prompt
    lines = []
    if calorie_goal:
        lines.append(f"## Meta calórica diária do usuário: {calorie_goal} kcal\n")

    # Exercises first — ensures they are never truncated away
    lines.append("## Exercícios dos últimos 7 dias\n")
    if exercises:
        for e in exercises:
            activity = e.get("activity", "?")
            cal = e.get("calories", 0)
            dur = e.get("duration_minutes")
            date = str(e.get("date", ""))[:10]
            dur_str = f", {dur} min" if dur else ""
            effort = e.get("effort_level")
            effort_str = f", esforço {effort}/10" if effort else ""
            lines.append(f"- [{date}] {activity} — {cal} kcal{dur_str}{effort_str}")
    else:
        lines.append("_Nenhum exercício registrado._")

    lines.append("\n## Refeições dos últimos 7 dias\n")
    if meals:
        for m in meals:
            food = m.get("food", "?")
            meal_type = m.get("meal_type", "?")
            qty = m.get("quantity", "")
            cal = m.get("calories", 0)
            date = str(m.get("date", ""))[:10]
            lines.append(f"- [{date}] {meal_type}: {food} ({qty}) — {cal} kcal")
    else:
        lines.append("_Nenhuma refeição registrada._")

    data_text = "\n".join(lines)
    if len(data_text) > 8000:
        data_text = data_text[:8000] + "\n... (dados truncados)"

    openai_client = _create_openai_client()
    llm_model = _get_llm_model()

    if logger:
        logger.info("Calling LLM for nutritional analysis (%d meals, %d exercises)...", len(meals), len(exercises))

    try:
        completion = _safe_openai_call(
            lambda: openai_client.responses.create(
                model=llm_model,
                instructions=_NUTRITIONAL_ANALYSIS_PROMPT,
                input=data_text,
            ),
            description="generate_nutritional_analysis",
        )
        return completion.output_text.strip()
    except OpenAICallError as exc:
        if logger:
            logger.error("Nutritional analysis LLM call failed: %s", exc)
        raise  # let the caller (endpoint) handle it and return proper error to the frontend


def transcribe_audio_input(audio_bytes, filename, mime_type, project_logger):
    if not audio_bytes:
        raise ValueError("audio_bytes is required")

    openai_client = _create_openai_client()
    transcribe_model = _get_audio_transcribe_model()
    safe_filename = str(filename or "audio_input.bin")
    if "." not in safe_filename:
        safe_filename = f"{safe_filename}.bin"
    safe_mime_type = str(mime_type or "application/octet-stream").strip() or "application/octet-stream"

    project_logger.info("Calling LLM to transcribe audio input...")
    transcription = _safe_openai_call(
        lambda: openai_client.audio.transcriptions.create(
            model=transcribe_model,
            file=(safe_filename, audio_bytes, safe_mime_type),
        ),
        description="transcribe_audio_input",
    )

    transcript_text = str(getattr(transcription, "text", "") or "").strip()
    if not transcript_text and isinstance(transcription, dict):
        transcript_text = str(transcription.get("text", "")).strip()
    if not transcript_text:
        raise ValueError("LLM returned empty audio transcription")
    return transcript_text


def summarize_day_context(today_tasks, today_events, project_logger):
    return summarize_period_context("hoje", today_tasks, today_events, project_logger)


def summarize_period_context(period_label, tasks, events, project_logger):
    if not tasks and not events:
        return _build_empty_period_message(period_label)

    openai_client = _create_openai_client()
    llm_model = _get_llm_model()

    project_logger.info("Calling LLM to summarize %s context...", period_label)
    completion = _safe_openai_call(
        lambda: openai_client.responses.create(
            model=llm_model,
            input=build_period_summary_prompt(period_label, tasks, events),
        ),
        description=f"summarize_period_context({period_label})",
    )
    return completion.output_text


def parse_add_task_output(output_text):
    payload = _extract_json_payload(output_text)
    task_name = str(payload.get("task_name", "")).strip()
    project = str(payload.get("project", "Pessoal")).strip() or "Pessoal"
    due_date = str(payload.get("due_date", "")).strip()
    tags = payload.get("tags", [])

    if not task_name:
        raise ValueError("LLM did not provide task_name")
    if not due_date:
        due_date = today_iso_in_configured_timezone()
    try:
        datetime.date.fromisoformat(due_date)
    except ValueError as error:
        raise ValueError("LLM did not provide a valid due_date (YYYY-MM-DD)") from error
    if not isinstance(tags, list):
        raise ValueError("LLM did not provide tags as a list")

    clean_tags = _sanitize_task_tags(tags)
    return {
        "task_name": task_name,
        "project": project,
        "due_date": due_date,
        "tags": clean_tags,
    }


def parse_add_event_output(output_text):
    payload = _extract_json_payload(output_text)
    summary = str(payload.get("summary", "")).strip()
    start_datetime = str(payload.get("start_datetime", "")).strip()
    end_datetime = str(payload.get("end_datetime", "")).strip()
    description = str(payload.get("description", "")).strip()
    default_timezone = _get_default_event_timezone()
    timezone = str(payload.get("timezone", default_timezone)).strip() or default_timezone

    if not summary:
        raise ValueError("LLM did not provide summary")
    _validate_event_datetime(start_datetime, "start_datetime")
    _validate_event_datetime(end_datetime, "end_datetime")

    if end_datetime <= start_datetime:
        raise ValueError("LLM provided end_datetime before or equal to start_datetime")

    return {
        "summary": summary,
        "start_datetime": start_datetime,
        "end_datetime": end_datetime,
        "description": description,
        "timezone": timezone,
    }


def parse_add_note_output(output_text):
    payload = _extract_json_payload(output_text)
    note_name = str(payload.get("note_name") or payload.get("name") or "").strip()
    tag = str(payload.get("tag", "")).strip()
    observations = str(payload.get("observations") or payload.get("notes") or "").strip()
    url = str(payload.get("url", "")).strip()

    if not note_name:
        raise ValueError("LLM did not provide note_name")
    if not tag:
        tag = _infer_note_tag(f"{note_name} {observations}")

    return {
        "note_name": note_name,
        "tag": tag,
        "observations": observations,
        "url": url,
    }


def _format_task_for_prompt(task):
    tags = ", ".join(task.get("tags", [])) if task.get("tags") else "sem tag"
    project = task.get("project", "No project")
    deadline = task.get("deadline", "sem data")
    overdue_label = _build_overdue_label(deadline)
    return (
        f"\n - {task['name']} | projeto: {project} | prazo: {deadline}"
        f" | status_prazo: {overdue_label} | tags: {tags}"
    )


def _build_overdue_label(deadline):
    if not deadline:
        return "NO PRAZO"
    try:
        deadline_date = datetime.date.fromisoformat(str(deadline).split("T")[0])
        return "ATRASADA" if deadline_date < today_in_configured_timezone() else "NO PRAZO"
    except ValueError:
        return "NO PRAZO"


def _extract_json_payload(output_text):
    text = str(output_text or "").strip()
    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("LLM did not return valid JSON")
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as error:
            raise ValueError("LLM did not return valid JSON") from error


def _sanitize_task_tags(tags):
    blocked_terms = {
        "amanha", "amanhã", "hoje", "ontem",
        "manha", "manhã", "tarde", "noite",
        "segunda", "terca", "terça", "quarta", "quinta", "sexta", "sabado", "sábado", "domingo",
    }
    clean = []
    for tag in tags:
        value = str(tag).strip()
        if not value:
            continue
        normalized = value.lower()
        if normalized in blocked_terms:
            continue
        clean.append(value)
    return clean


def _infer_note_tag(content):
    text = str(content or "").lower()
    if any(keyword in text for keyword in ("reunião", "reuniao", "meeting", "call", "1:1")):
        return "MEETING"
    if any(keyword in text for keyword in ("ideia", "idea", "brainstorm", "insight")):
        return "IDEA"
    if any(keyword in text for keyword in ("bug", "erro", "falha", "issue")):
        return "BUG"
    if any(keyword in text for keyword in ("estudo", "study", "curso", "aprender", "learn")):
        return "STUDY"
    if any(keyword in text for keyword in ("saúde", "saude", "treino", "health")):
        return "HEALTH"
    return "GENERAL"


def _validate_event_datetime(value, field_name):
    try:
        datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except ValueError as error:
        raise ValueError(f"LLM did not provide a valid {field_name} (YYYY-MM-DDTHH:MM)") from error


def build_calendar_events_prompt(events):
    event_lines = "".join(
        f"\n - {event.get('summary', 'Sem título')} | start: {event.get('start')} | end: {event.get('end')} | location: {event.get('location') or 'N/A'}"
        for event in events
    )
    return f"{CALENDAR_SUMMARY_PROMPT}\n\nEventos:{event_lines}"


def build_day_summary_prompt(today_tasks, today_events):
    return build_period_summary_prompt("hoje", today_tasks, today_events)


def build_period_summary_prompt(period_label, tasks, events):
    period_key = str(period_label or "hoje").strip().lower()
    summary_title = _build_period_summary_title(period_key)
    empty_target = _build_period_empty_target(period_key)
    empty_message = _build_empty_period_message(period_key)
    section_tasks = _build_period_task_section_title(period_key)
    section_events = _build_period_event_section_title(period_key)
    temporal_context = _build_temporal_prompt_context()

    if _is_week_period(period_key):
        prompt_header = (
            f"Você é um assistente pessoal e deve gerar um resumo {summary_title} em português."
            "\nFormato obrigatório em Markdown:"
            f"\n## Resumo {summary_title}"
            f"\n### {section_tasks}"
            "\n- 3 a 6 bullets curtos agrupando prioridades por contexto/projeto."
            f"\n### {section_events}"
            "\n- 3 a 6 bullets com blocos importantes, conflitos e janelas livres."
            "\n### Foco recomendado"
            "\n- 1 a 3 bullets curtos com prioridade e próximo passo."
            "\nRegras:"
            "\n- Seja objetivo, claro e organizado."
            "\n- Não responder em JSON."
            "\n- Não liste todas as tarefas ou eventos individualmente; sintetize os principais pontos."
            "\n- Tarefas com prazo anterior a hoje são CRÍTICAS e devem ser mencionadas primeiro."
            f"\n- Se não houver tarefas e nem eventos para {empty_target}, responda exatamente:"
            f"\n\"{empty_message.replace(chr(10), '\\\\n')}\""
            f"\n\n{temporal_context}"
        )
    else:
        prompt_header = (
            f"Você é um assistente pessoal e deve gerar um resumo {summary_title} em português."
            "\nFormato obrigatório em Markdown:"
            f"\n## Resumo {summary_title}"
            f"\n### {section_tasks}"
            "\n- **[ATRASADA] ou [NO PRAZO]** — Tarefa (Projeto) [Tags]"
            f"\n### {section_events}"
            "\n- **HH:MM ou Dia inteiro** — Evento (local opcional)"
            "\n### Foco recomendado"
            "\n- Mencione a tarefa mais importante do período."
            "\n- Até 2 bullets adicionais com próximos passos concretos."
            "\nRegras:"
            "\n- Seja objetivo, claro e organizado."
            "\n- Não responder em JSON."
            "\n- Tarefas com prazo anterior a hoje devem ser marcadas [ATRASADA]; demais, [NO PRAZO]."
            f"\n- Se não houver tarefas e nem eventos para {empty_target}, responda exatamente:"
            f"\n\"{empty_message.replace(chr(10), '\\\\n')}\""
            f"\n\n{temporal_context}"
        )

    task_lines = "".join(
        f"\n - {task.get('name', 'Sem nome')} | projeto: {task.get('project', 'Sem projeto')} | "
        f"deadline: {task.get('deadline', 'sem data')} | tags: {', '.join(task.get('tags', [])) if task.get('tags') else 'sem tags'}"
        for task in tasks
    ) or "\n - Sem tarefas"

    event_lines = "".join(
        f"\n - {event.get('summary', 'Sem título')} | start: {event.get('start', 'sem início')} | "
        f"end: {event.get('end', 'sem fim')} | location: {event.get('location') or 'N/A'}"
        for event in events
    ) or "\n - Sem eventos"

    return f"{prompt_header}\n\n{section_tasks}:{task_lines}\n\n{section_events}:{event_lines}"


def _build_empty_period_message(period_key):
    summary_title = _build_period_summary_title(period_key)
    empty_target = _build_period_empty_target(period_key)
    return f"## Resumo {summary_title}\n\nSem tarefas e sem eventos para {empty_target}."


def _build_period_summary_title(period_key):
    if period_key in ("amanha", "amanhã", "tomorrow"):
        return "de amanhã"
    if period_key in ("semana", "semana atual", "week"):
        return "da semana atual"
    return "de hoje"


def _build_period_empty_target(period_key):
    if period_key in ("amanha", "amanhã", "tomorrow"):
        return "amanhã"
    if period_key in ("semana", "semana atual", "week"):
        return "esta semana"
    return "hoje"


def _build_period_task_section_title(period_key):
    if period_key in ("amanha", "amanhã", "tomorrow"):
        return "Tarefas de amanhã"
    if period_key in ("semana", "semana atual", "week"):
        return "Tarefas da semana"
    return "Tarefas de hoje"


def _build_period_event_section_title(period_key):
    if period_key in ("amanha", "amanhã", "tomorrow"):
        return "Agenda de amanhã"
    if period_key in ("semana", "semana atual", "week"):
        return "Agenda da semana"
    return "Agenda de hoje"


def _is_week_period(period_key):
    return period_key in ("semana", "semana atual", "week")


def _get_default_event_timezone():
    configured_timezone = get_configured_timezone_name()
    try:
        ZoneInfo(configured_timezone)
        return configured_timezone
    except ZoneInfoNotFoundError:
        return "America/Sao_Paulo"


def _build_temporal_prompt_context():
    time_context = build_time_context()
    return (
        "Contexto temporal operacional do usuário:\n"
        f"- Timezone: {time_context['timezone_name']} (UTC offset {time_context['local_utc_offset']})\n"
        f"- Data local atual: {time_context['local_date_iso']}\n"
        f"- Horário local atual: {time_context['local_now_iso']}\n"
        "- Regra: interprete termos relativos de tempo (hoje, amanhã, agora, esta semana) usando este timezone."
    )


def build_message(tasks):
    task_lines = "".join(_format_task_for_prompt(task) for task in tasks)

    for prompt_path in (PROMPT_FILE_PATH, PROMPT_TEMPLATE_FILE_PATH):
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as prompt_file:
                prompt = prompt_file.read().rstrip()
            return f"{prompt}{task_lines}"

    return f"{DEFAULT_PROMPT}{task_lines}"


_openai_client_lock = threading.Lock()
_openai_client_instance: openai.OpenAI | None = None


def _create_openai_client():
    """Return a shared OpenAI client, creating it on first call."""
    global _openai_client_instance
    if _openai_client_instance is not None:
        return _openai_client_instance
    with _openai_client_lock:
        if _openai_client_instance is not None:
            return _openai_client_instance
        openai_api_key = os.getenv("OPENAI_KEY")
        if not openai_api_key:
            raise ValueError("Missing required environment variable: OPENAI_KEY")
        timeout_seconds = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60"))
        _openai_client_instance = openai.OpenAI(
            api_key=openai_api_key, timeout=timeout_seconds,
        )
        return _openai_client_instance


def _get_llm_model():
    llm_model = str(os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL)).strip()
    return llm_model or DEFAULT_LLM_MODEL


def _get_audio_transcribe_model():
    transcribe_model = str(os.getenv("AUDIO_TRANSCRIBE_MODEL", DEFAULT_AUDIO_TRANSCRIBE_MODEL)).strip()
    return transcribe_model or DEFAULT_AUDIO_TRANSCRIBE_MODEL
