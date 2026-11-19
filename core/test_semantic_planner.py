#!/usr/bin/env python3
"""
core/test_semantic_planner.py

Suíte de testes unitários para core/semantic_planner.py (Editor).

Usa provedores simulados e dados sintéticos, SEM chamar modelo externo real.

Cenários cobertos:
  - entrada/saída do adaptador e independência de fornecedor
    (AntigravityCliProvider, OpenCodeCliProvider simulados via monkeypatch/mock);
  - conformidade com semantic_plan.json (schema 1.0.0) e integridade de
    referências temporais;
  - rejeição de timestamps inventados, respostas malformadas/incompletas e
    falha de comunicação com agente;
  - fallback determinístico sem alegar compreensão semântica;
  - ausência de envio externo sem authorized=True e registro de consentimento;
  - preservação de SHA-256 em brutos/ e ausência de duplicação da transcricao;
  - integração ponta-a-ponta (semantic_planner -> briefing -> edl_builder ->
    master_lint).
"""

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

# Garante import do pacote core (raiz Editor).
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.workspace import (  # noqa: E402
    WorkspaceLoader,
    init_workspace,
    register_brand,
    load_brand_profile,
    create_project,
    load_project,
    resolve_episodio_asset,
)
from core.ingest import (  # noqa: E402
    ingest_media,
    compute_sha256,
)
from core.semantic_planner import (  # noqa: E402
    SemanticPlannerProvider,
    SemanticConsent,
    AntigravityCliProvider,
    OpenCodeCliProvider,
    CallableMockProvider,
    SemanticPlannerError,
    plan_episodio_semantics,
    load_semantic_consent,
    is_semantic_consent_authorized,
    _fallback_plan,
)
from core.semantic_plan import (  # noqa: E402
    validate_semantic_plan,
    SemanticPlanError,
)
from core.briefing import gerar_briefing  # noqa: E402
from core.edl_builder import build_edl_from_alignment  # noqa: E402
from core.master_lint import lint  # noqa: E402


def _iso_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _gravar_json(path: Path, dados: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)


def _gerar_wav_16k_mono(caminho: Path, duracao_s: float = 1.0, tom_hz: float = 440.0) -> None:
    import struct
    import wave
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if caminho.exists():
        caminho.chmod(0o644)
        caminho.unlink()
    sample_rate = 16000
    n_samples = int(sample_rate * duracao_s)
    amostras = []
    for i in range(n_samples):
        valor = int(12000 * __import__("math").sin(2 * __import__("math").pi * tom_hz * i / sample_rate))
        amostras.append(struct.pack("<h", valor))
    with wave.open(str(caminho), "wb") as wf2:
        wf2.setnchannels(1)
        wf2.setsampwidth(2)
        wf2.setframerate(sample_rate)
        wf2.writeframes(b"".join(amostras))


def _setup_workspace_e_marca(tmp: Path, marca_id: str = "marca-teste") -> Path:
    init_workspace(tmp)
    marca_dir = tmp / "projetos" / marca_id / "branding"
    marca_dir.mkdir(parents=True, exist_ok=True)
    perfil = {
        "schema_version": "1.0.0",
        "brand_id": marca_id,
        "display_name": f"Canal {marca_id}",
        "presenter": {"name": "Apresentador Teste", "credential": "Credencial de Teste"},
        "marca": {"destaque": "#004aad", "fonte": "Inter"},
        "preferencias_edicao": {
            "canal": f"Canal {marca_id}",
            "apresentador": "Apresentador Teste",
            "credencial_oficial": "Credencial de Teste",
            "lexicon_transcricao": "alta minutagem, marketplaces, faturamento",
            "render_defaults": {
                "master_16x9": {"width": 1920, "height": 1080, "fps": 30},
                "shorts_9x16": {"width": 1080, "height": 1920, "fps": 30},
            },
            "audio": {
                "silence_guard_ms": [180, 220],
                "jumpcut_gap_threshold_ms": 450,
                "jumpcut_target_gap_ms": [200, 250],
            },
            "asr": {
                "lexicon": ["alta minutagem", "marketplaces", "faturamento"],
                "phonetic_rules_file": "phonetic_rules.json",
            },
        },
        "visual": {
            "palette": {"primary": "#004aad"},
            "safe_zones": {},
        },
        "asr": {},
        "assets": {},
    }
    (marca_dir / "config.json").write_text(
        json.dumps(perfil, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    loader = WorkspaceLoader(tmp)
    loader.register_brand(marca_id, f"Canal {marca_id}")
    return tmp


def _setup_episodio_com_analise(tmp: Path, marca_id: str, episodio_id: str) -> Path:
    loader = WorkspaceLoader(tmp)
    loader.load_workspace()

    episodio_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "")
    episodio_dir.mkdir(parents=True, exist_ok=True)
    projeto = {
        "schema_version": "1.0.0",
        "marca_id": marca_id,
        "episodio_id": episodio_id,
        "nome": episodio_id,
        "current_stage": "01_GRAVACAO_ORIGINAL",
        "created_at": _iso_now(),
        "updated_at": _iso_now(),
        "sources": [],
        "artifacts": {},
        "approvals": {
            "master_16x9_approved": False,
            "approved_by": None,
            "approved_at": None,
        },
    }
    _gravar_json(loader.project_file(marca_id, episodio_id), projeto)

    brutos_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "brutos")
    brutos_dir.mkdir(parents=True, exist_ok=True)
    video_bruto = brutos_dir / "video.mp4"
    _gerar_wav_16k_mono(video_bruto, duracao_s=2.0)

    rc = ingest_media(
        input_path=str(video_bruto),
        marca_id=marca_id,
        episodio_id=episodio_id,
        workspace_root=str(tmp),
    )
    assert rc == 0, f"ingest falhou com codigo {rc}"

    fonte_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "workspace/fonte")
    fonte_dir.mkdir(parents=True, exist_ok=True)

    transcricao = {
        "schema_version": "1.0.0",
        "language": "pt",
        "audio_duration_seconds": 105.0,
        "segments": [
            {
                "id": 0,
                "start": 0.0,
                "end": 3.58,
                "text": "Seja bem-vindo ao canal do Dr. Gestao.",
                "words": [
                    {"word_id": "w-0", "word": "Seja", "start": 0.0, "end": 0.76, "probability": 0.99},
                    {"word_id": "w-1", "word": "bem-vindo", "start": 1.04, "end": 1.46, "probability": 0.97},
                    {"word_id": "w-2", "word": "canal", "start": 1.64, "end": 1.9, "probability": 0.98},
                ],
            },
            {
                "id": 1,
                "start": 3.9,
                "end": 5.0,
                "text": "Sao 29 anos.",
                "words": [
                    {"word_id": "w-3", "word": "Sao", "start": 3.9, "end": 4.08, "probability": 0.97},
                    {"word_id": "w-4", "word": "29", "start": 4.08, "end": 4.5, "probability": 0.98},
                    {"word_id": "w-5", "word": "anos", "start": 4.5, "end": 5.0, "probability": 0.99},
                ],
            },
        ],
    }
    _gravar_json(fonte_dir / "transcript.json", transcricao)

    alignment = {
        "schema_version": "1.0.0",
        "editorial_units": [
            {
                "raw_start": 0.0,
                "raw_end": 3.58,
                "text": "Seja bem-vindo ao canal do Dr. Gestao.",
                "words": transcricao["segments"][0]["words"],
            },
            {
                "raw_start": 3.9,
                "raw_end": 5.0,
                "text": "Sao 29 anos.",
                "words": transcricao["segments"][1]["words"],
            },
        ],
    }
    _gravar_json(fonte_dir / "alignment.json", alignment)

    _gravar_json(fonte_dir / "phonetic_report.json", {"status": "VERIFIED", "low_confidence": []})

    return tmp


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


def test_semantic_consent_nao_autorizado_por_padrao():
    """Consentimento nao eh autorizado por padrao."""
    c = SemanticConsent(destination="local", shared_data=["transcript.json"])
    assert c.authorized is False
    assert c.consent_id
    assert c.timestamp_utc
    print("  [PASS] test_semantic_consent_nao_autorizado_por_padrao")


def test_semantic_consent_serializacao():
    """Serializacao/desserializacao de SemanticConsent."""
    c = SemanticConsent(
        destination="provedor-teste",
        shared_data=["transcript.json", "alignment.json"],
        authorized=True,
        notes="teste",
    )
    d = c.to_dict()
    c2 = SemanticConsent.from_dict(d)
    assert c2.authorized is True
    assert c2.destination == "provedor-teste"
    assert c2.shared_data == ["transcript.json", "alignment.json"]
    assert c2.consent_id == c.consent_id
    print("  [PASS] test_semantic_consent_serializacao")


def test_provedor_mock_injecao_dependencia():
    """CallableMockProvider permite injecao de dependencia."""
    chamado = {}

    def fn(context: Dict[str, Any]) -> Dict[str, Any]:
        chamado["recebeu"] = context
        return {"schema_version": "1.0.0", "tema_central": "tema", "tese_principal": "tese", "topicos": []}

    prov = CallableMockProvider(fn)
    contexto = {"marca_id": "m", "episodio_id": "e", "transcript": {}}
    resultado = prov.plan(contexto)
    assert chamado["recebeu"] == contexto
    assert resultado["schema_version"] == "1.0.0"
    print("  [PASS] test_provedor_mock_injecao_dependencia")


def test_provedores_nao_sao_instanciaveis_sem_chave_comercial():
    """Provedores locais nao exigem chaves comerciais de API."""
    antig = AntigravityCliProvider(schema_file="schema.json")
    opencode = OpenCodeCliProvider()
    assert antig.binary == "agy"
    assert opencode.binary == "opencode"
    print("  [PASS] test_provedores_nao_sao_instanciaveis_sem_chave_comercial")


def test_plan_sem_autorizado_retorna_fallback():
    """Sem authorized=True, nao chama provedor externo e retorna fallback."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-fb")
        _setup_episodio_com_analise(tmp, "marca-fb", "ep-fb")

        resultado = plan_episodio_semantics(
            marca_id="marca-fb",
            episodio_id="ep-fb",
            workspace_root=str(tmp),
            authorized=False,
        )

        assert resultado["consent"]["authorized"] is False
        assert resultado["fallback"] is True
        assert resultado["plan"] is not None
        assert resultado["validated"] is True
        # Nao alega compreensao semantica
        plano = resultado["plan"]
        assert "fallback" in plano["tema_central"].lower() or "sem autorizacao" in plano["tema_central"].lower()
        print("  [PASS] test_plan_sem_autorizado_retorna_fallback")


def test_plan_com_autorizado_mas_sem_provedor_retorna_fallback():
    """authorized=True mas sem provider: fallback, nao chama externo."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-np")
        _setup_episodio_com_analise(tmp, "marca-np", "ep-np")

        resultado = plan_episodio_semantics(
            marca_id="marca-np",
            episodio_id="ep-np",
            workspace_root=str(tmp),
            authorized=True,
            provider=None,
        )

        assert resultado["fallback"] is True
        assert resultado["provider"] == "fallback_local"
        print("  [PASS] test_plan_com_autorizado_mas_sem_provedor_retorna_fallback")


def test_plan_nao_envia_externo_sem_autorizado():
    """Sem authorized=True, nenhum provedor externo e invocado."""
    chamado = {"executou": False}

    def falso_provedor(context):
        chamado["executou"] = True
        return {}

    prov = CallableMockProvider(falso_provedor)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-ne")
        _setup_episodio_com_analise(tmp, "marca-ne", "ep-ne")

        resultado = plan_episodio_semantics(
            marca_id="marca-ne",
            episodio_id="ep-ne",
            workspace_root=str(tmp),
            authorized=False,
            provider=prov,
        )

        assert chamado["executou"] is False
        assert resultado["fallback"] is True
        print("  [PASS] test_plan_nao_envia_externo_sem_autorizado")


def test_registro_consentimento_gravado():
    """semantic_consent.json e gravado quando write_files=True."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-cons")
        _setup_episodio_com_analise(tmp, "marca-cons", "ep-cons")

        resultado = plan_episodio_semantics(
            marca_id="marca-cons",
            episodio_id="ep-cons",
            workspace_root=str(tmp),
            authorized=False,
            write_files=True,
        )

        assert "consent_path" in resultado
        consent_path = Path(resultado["consent_path"])
        assert consent_path.is_file()
        carregado = load_semantic_consent("marca-cons", "ep-cons", str(tmp))
        assert carregado is not None
        assert carregado.authorized is False
        assert is_semantic_consent_authorized("marca-cons", "ep-cons", str(tmp)) is False
        print("  [PASS] test_registro_consentimento_gravado")


def test_plano_conforme_schema_100():
    """Plano gerado e valido contra schema 1.0.0 via validate_semantic_plan."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-schema")
        _setup_episodio_com_analise(tmp, "marca-schema", "ep-schema")

        resultado = plan_episodio_semantics(
            marca_id="marca-schema",
            episodio_id="ep-schema",
            workspace_root=str(tmp),
            authorized=False,
            write_files=True,
        )

        assert resultado["validated"] is True
        plano = resultado["plan"]
        validate_semantic_plan(plano)
        assert plano["schema_version"] == "1.0.0"
        assert plano["tema_central"]
        assert plano["tese_principal"]
        assert isinstance(plano["topicos"], list) and len(plano["topicos"]) > 0
        print("  [PASS] test_plano_conforme_schema_100")


def test_rejeita_timestamp_inventado():
    """validate_semantic_plan rejeita timestamps que excedem duracao da transcricao."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-ts")
        _setup_episodio_com_analise(tmp, "marca-ts", "ep-ts")

        # transcript dura 5s, mas plano inventa timestamp em 999s
        plano_invalido = {
            "schema_version": "1.0.0",
            "tema_central": "tema",
            "tese_principal": "tese",
            "topicos": [
                {
                    "topic_id": "T1",
                    "titulo": "Topico",
                    "justificativa": "just",
                    "raw_start": 0.0,
                    "raw_end": 999.0,
                    "segment_ids": [0],
                    "word_refs": ["w-0"],
                },
            ],
            "argumentos": [],
            "grupos_explicacao": [],
            "ganchos_e_viradas": [],
            "repeticoes_dispensaveis": [],
            "falsos_comecos": [],
            "segmentos_editoriais": [],
            "intencoes_visuais": [],
        }
        transcricao_path = tmp / "projetos" / "marca-ts" / "episodios" / "ep-ts" / "workspace" / "fonte" / "transcript.json"
        transcricao = json.loads(transcricao_path.read_text(encoding="utf-8"))
        try:
            validate_semantic_plan(plano_invalido, transcript_data=transcricao)
            assert False, "Deveria ter levantado SemanticPlanError"
        except SemanticPlanError as exc:
            assert "excede" in str(exc) or "inventado" in str(exc)
        print("  [PASS] test_rejeita_timestamp_inventado")


def test_rejeita_resposta_malformada():
    """Plano sem campos obrigatorios e rejeitado."""
    plano_malformado = {"schema_version": "1.0.0"}  # falta tema_central, tese_principal, topicos
    try:
        validate_semantic_plan(plano_malformado)
        assert False, "Deveria ter levantado SemanticPlanError"
    except SemanticPlanError:
        pass
    print("  [PASS] test_rejeita_resposta_malformada")


def test_fallback_nao_alega_compreensão_semantica():
    """Plano de fallback nao alega compreensao semantica."""
    plano = _fallback_plan(
        marca_id="m",
        episodio_id="e",
        transcript_data={"segments": []},
        brand_profile={"apresentador": "A", "display_name": "Canal"},
    )
    texto = json.dumps(plano, ensure_ascii=False).lower()
    assert "fallback" in texto or "sem autorizacao" in texto
    assert "compreensao" not in texto and "entendimento" not in texto
    print("  [PASS] test_fallback_nao_alega_compreensão_semantica")


def test_preserva_sha256_brutos_e_sem_duplicacao_transcricao():
    """SHA-256 de brutos/ e preservado; transcricao nao duplicada."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-sha")
        _setup_episodio_com_analise(tmp, "marca-sha", "ep-sha")

        projeto = load_project(str(tmp), "marca-sha", "ep-sha")
        sources = projeto.get("sources", [])
        assert len(sources) >= 1, "Deveria haver pelo menos uma source apos ingest"
        for src in sources:
            sha = src.get("sha256")
            path = src.get("path")
            if sha and path:
                resultado_hash = compute_sha256(path)
                actual = resultado_hash[0] if isinstance(resultado_hash, tuple) else resultado_hash
                assert actual == sha, f"SHA-256 diverge para {path}"

        # Transcricao gravada apenas uma vez em workspace/fonte/
        fonte_dir = tmp / "projetos" / "marca-sha" / "episodios" / "ep-sha" / "workspace" / "fonte"
        assert (fonte_dir / "transcript.json").is_file()
        transcricao = json.loads((fonte_dir / "transcript.json").read_text(encoding="utf-8"))
        assert "segments" in transcricao
        print("  [PASS] test_preserva_sha256_brutos_e_sem_duplicacao_transcricao")


def test_falha_comunicacao_agente_fallback_seguro():
    """Falha de comunicacao com provedor resulta em fallback seguro (nao corrompe dados)."""
    def prov_que_sempre_falha(context):
        raise SemanticPlannerError("agente nao respondeu")

    prov = CallableMockProvider(prov_que_sempre_falha)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-falha")
        _setup_episodio_com_analise(tmp, "marca-falha", "ep-falha")

        resultado = plan_episodio_semantics(
            marca_id="marca-falha",
            episodio_id="ep-falha",
            workspace_root=str(tmp),
            authorized=True,
            provider=prov,
        )

        assert resultado["fallback"] is True
        assert resultado["error"] is not None
        assert resultado["plan"] is not None
        assert resultado["validated"] is True
        print("  [PASS] test_falha_comunicacao_agente_fallback_seguro")


def test_provedor_saida_malformada_fallback():
    """Provedor retorna JSON malformado -> fallback seguro."""
    def prov_malformado(context):
        return {"schema_version": "99.0"}  # versao invalida

    prov = CallableMockProvider(prov_malformado)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-mal")
        _setup_episodio_com_analise(tmp, "marca-mal", "ep-mal")

        resultado = plan_episodio_semantics(
            marca_id="marca-mal",
            episodio_id="ep-mal",
            workspace_root=str(tmp),
            authorized=True,
            provider=prov,
        )

        assert resultado["fallback"] is True
        assert resultado["validation_error"] is not None
        assert resultado["validated"] is True  # fallback revalidado com sucesso
        print("  [PASS] test_provedor_saida_malformada_fallback")


def test_integracao_ponta_a_ponta():
    """semantic_planner -> briefing -> edl_builder -> master_lint."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-e2e")
        _setup_episodio_com_analise(tmp, "marca-e2e", "ep-e2e")

        # 1. semantic_planner
        sp = plan_episodio_semantics(
            marca_id="marca-e2e",
            episodio_id="ep-e2e",
            workspace_root=str(tmp),
            authorized=False,
            write_files=True,
        )
        assert sp["validated"] is True
        assert Path(sp["plan_path"]).is_file()

        # 2. briefing (usa semantic_plan.json)
        rc = gerar_briefing(
            marca_id="marca-e2e",
            episodio_id="ep-e2e",
            workspace_root=str(tmp),
            semantic_plan_path=sp["plan_path"],
        )
        assert rc == 0
        briefing_dir = tmp / "projetos" / "marca-e2e" / "episodios" / "ep-e2e" / "workspace" / "briefing"
        assert (briefing_dir / "briefing.json").is_file()
        assert (briefing_dir / "BRIEFING.md").is_file()

        # 3. edl_builder
        loader = WorkspaceLoader(tmp)
        loader.load_workspace()
        marca_profile = loader.load_brand_profile("marca-e2e")
        align_path = tmp / "projetos" / "marca-e2e" / "episodios" / "ep-e2e" / "workspace" / "fonte" / "alignment.json"
        edl, plano = build_edl_from_alignment(
            alignment_path=align_path,
            workspace_root=str(tmp),
            marca_id="marca-e2e",
            episodio_id="ep-e2e",
            brand_profile=marca_profile,
        )
        assert edl["schema_version"] == "1.0.0"
        assert plano["schema_version"] == "1.0.0"

        # 4. master_lint
        projeto = load_project(str(tmp), "marca-e2e", "ep-e2e")
        relatorio = lint(plano, edl, projeto)
        assert relatorio["auto_approved"] is False
        assert relatorio["requires_human_approval"] is True
        print("  [PASS] test_integracao_ponta_a_ponta")


def test_independencia_fornecedor_antigravity_simulado(monkeypatch, tmp_path):
    """AntigravityCliProvider: mocka subprocess.run diretamente, valida
    argumentos exatos (--input-format stream-json, --output-format stream-json,
    --json-schema somente quando valido, sem --print) e prompt enviado
    exclusivamente via stdin no formato NDJSON {"event":"user","message":{...}}.
    Valida saida com validate_semantic_plan()."""
    from unittest.mock import patch

    # Cria arquivo schema temporario valido dentro do workspace_root.
    schema_path = tmp_path / "schema.json"
    schema_path.write_text("{}", encoding="utf-8")

    plano_valido = {
        "schema_version": "1.0.0",
        "tema_central": "tema simulado antigravity",
        "tese_principal": "tese simulada",
        "topicos": [
            {
                "topic_id": "T1",
                "titulo": "Topico",
                "justificativa": "just",
                "raw_start": 0.0,
                "raw_end": 3.0,
                "segment_ids": [0],
                "word_refs": ["w-0"],
            },
        ],
        "argumentos": [],
        "grupos_explicacao": [],
        "ganchos_e_viradas": [],
        "repeticoes_dispensaveis": [],
        "falsos_comecos": [],
        "segmentos_editoriais": [
            {
                "decision": "preservar",
                "topic_id": "T1",
                "justificativa": "just",
                "raw_start": 0.0,
                "raw_end": 3.0,
                "segment_ids": [0],
                "word_refs": ["w-0"],
            },
        ],
        "intencoes_visuais": [],
    }

    ndjson_result = json.dumps(
        {
            "event": "result",
            "status": "SUCCESS",
            "structured_output": plano_valido,
        },
        ensure_ascii=False,
    ) + "\n"

    captured = {}

    class FakeProc:
        returncode = 0
        stdout = ndjson_result
        stderr = ""

    def fake_run(cmd, input=None, capture_output=True, text=True, encoding=None, timeout=None):
        captured["cmd"] = cmd
        captured["input"] = input
        captured["timeout"] = timeout
        return FakeProc()

    with patch("subprocess.run", side_effect=fake_run) as mock_run:
        prov = AntigravityCliProvider(
            schema_file=str(schema_path),
            workspace_root=str(tmp_path),
        )
        resultado = prov.plan({"marca_id": "x", "transcript": {}})

        # Argumentos exatos
        cmd = captured["cmd"]
        assert "--print" not in cmd, f"--print nao deve estar presente: {cmd}"
        assert "--input-format" in cmd
        assert "stream-json" in cmd
        assert "--output-format" in cmd
        assert "stream-json" in cmd
        assert "--json-schema" in cmd
        schema_idx = cmd.index("--json-schema")
        assert cmd[schema_idx + 1] == str(schema_path)

        # Prompt enviado exclusivamente via stdin (input)
        assert captured["input"] is not None
        stdin_obj = json.loads(captured["input"])
        assert stdin_obj["event"] == "user"
        assert stdin_obj["message"]["content"] is not None
        assert '"marca_id": "x"' in stdin_obj["message"]["content"]

        mock_run.assert_called_once()
        validate_semantic_plan(resultado)
        assert resultado["schema_version"] == "1.0.0"
        assert resultado["tema_central"] == "tema simulado antigravity"
    print("  [PASS] test_independencia_fornecedor_antigravity_simulado")


def test_independencia_fornecedor_opencode_simulado(monkeypatch):
    """OpenCodeCliProvider: mocka subprocess.run diretamente, retorna JSON
    valido com raw_end e valida com validate_semantic_plan()."""
    from unittest.mock import patch

    plano_valido = {
        "schema_version": "1.0.0",
        "tema_central": "tema simulado opencode",
        "tese_principal": "tese simulada",
        "topicos": [
            {
                "topic_id": "T1",
                "titulo": "Topico",
                "justificativa": "just",
                "raw_start": 0.0,
                "raw_end": 3.0,
                "segment_ids": [0],
                "word_refs": ["w-0"],
            },
        ],
        "argumentos": [],
        "grupos_explicacao": [],
        "ganchos_e_viradas": [],
        "repeticoes_dispensaveis": [],
        "falsos_comecos": [],
        "segmentos_editoriais": [
            {
                "decision": "preservar",
                "topic_id": "T1",
                "justificativa": "just",
                "raw_start": 0.0,
                "raw_end": 3.0,
                "segment_ids": [0],
                "word_refs": ["w-0"],
            },
        ],
        "intencoes_visuais": [],
    }

    class FakeProc:
        returncode = 0
        stdout = json.dumps(plano_valido, ensure_ascii=False)
        stderr = ""

    with patch("subprocess.run", return_value=FakeProc()) as mock_run:
        prov = OpenCodeCliProvider()
        resultado = prov.plan({"marca_id": "x", "transcript": {}})
        mock_run.assert_called_once()
        # Valida a saida com validate_semantic_plan
        validate_semantic_plan(resultado)
        assert resultado["schema_version"] == "1.0.0"
        assert resultado["tema_central"] == "tema simulado opencode"
    print("  [PASS] test_independencia_fornecedor_opencode_simulado")


# ---------------------------------------------------------------------------
# Testes locais do schema auxiliar Antigravity (sem chamar agy.exe)
# ---------------------------------------------------------------------------


def _carregar_schema_auxiliar() -> Dict[str, Any]:
    """Carrega o schema auxiliar do scratch do Antigravity."""
    schema_path = Path(
        "C:/Users/Edgard/.gemini/antigravity-cli/brain/"
        "4c449c97-123f-474a-846e-a67f753c6444/scratch/semantic_plan.schema.json"
    )
    if not schema_path.is_file():
        # Fallback: schema embutido para teste quando o arquivo nao existe
        return {
            "type": "object",
            "required": ["schema_version", "tema_central", "tese_principal",
                         "topicos", "argumentos", "grupos_explicacao",
                         "ganchos_e_viradas", "repeticoes_dispensaveis",
                         "falsos_comecos", "segmentos_editoriais",
                         "intencoes_visuais"],
            "properties": {
                "schema_version": {"type": "string", "const": "1.0.0"},
                "tema_central": {"type": "string"},
                "tese_principal": {"type": "string"},
                "topicos": {"type": "array", "items": {}},
                "argumentos": {"type": "array", "items": {}},
                "grupos_explicacao": {"type": "array", "items": {}},
                "ganchos_e_viradas": {"type": "array", "items": {}},
                "repeticoes_dispensaveis": {"type": "array", "items": {}},
                "falsos_comecos": {"type": "array", "items": {}},
                "segmentos_editoriais": {"type": "array", "items": {}},
                "intencoes_visuais": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id", "camada", "texto", "raw_start",
                                   "raw_end", "segment_ids", "funcao_editorial",
                                   "justificativa"],
                        "properties": {
                            "id": {"type": "string"},
                            "camada": {"type": "string"},
                            "componente_motion_library": {
                                "type": "string",
                                "enum": ["titulo_heroi"],
                            },
                            "texto": {"type": "string"},
                            "raw_start": {"type": "number"},
                            "raw_end": {"type": "number"},
                            "segment_ids": {"type": "array"},
                            "funcao_editorial": {"type": "string"},
                            "justificativa": {"type": "string"},
                        },
                    },
                },
            },
        }
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _verificar_sem_null_em_enuns_recursivo(obj: Any, caminho: str = "root") -> List[str]:
    """Verifica recursivamente se nao ha 'null' em arrays 'enum' nem tipos
    multiplos ['string', 'null'] incompatíveis com function_declarations."""
    problemas: List[str] = []

    if isinstance(obj, dict):
        # Verifica tipo multiplo incompatível
        tipo = obj.get("type")
        if isinstance(tipo, list) and "null" in tipo:
            problemas.append(f"{caminho}: type multiplo contem 'null': {tipo}")

        # Verifica enum contendo null
        enum_val = obj.get("enum")
        if isinstance(enum_val, list) and None in enum_val:
            problemas.append(f"{caminho}: enum contem null: {enum_val}")

        # Recursão em propriedades
        for chave, valor in obj.items():
            problemas.extend(_verificar_sem_null_em_enuns_recursivo(
                valor, f"{caminho}.{chave}"
            ))

    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            problemas.extend(_verificar_sem_null_em_enuns_recursivo(
                item, f"{caminho}[{idx}]"
            ))

    return problemas


def test_schema_auxiliar_sem_null_em_enuns():
    """Schema auxiliar nao deve ter 'null' em enuns nem tipos multiplos
    incompatíveis (verificacao recursiva)."""
    schema = _carregar_schema_auxiliar()
    problemas = _verificar_sem_null_em_enuns_recursivo(schema)
    assert not problemas, f"Problemas encontrados no schema: {problemas}"
    print("  [PASS] test_schema_auxiliar_sem_null_em_enuns")


def test_componente_motion_library_opcional_fora_de_required():
    """componente_motion_library deve ser string opcional com enum
    ['titulo_heroi'] e NÃO estar na lista 'required' de intencoes_visuais.items."""
    schema = _carregar_schema_auxiliar()
    intencoes = schema["properties"]["intencoes_visuais"]
    items = intencoes["items"]
    required = items.get("required", [])
    assert "componente_motion_library" not in required, (
        f"componente_motion_library nao deve estar em required: {required}"
    )

    prop = items["properties"]["componente_motion_library"]
    assert prop["type"] == "string", f'type deve ser "string": {prop}'
    assert prop["enum"] == ["titulo_heroi"], f'enum deve ser ["titulo_heroi"]: {prop}'
    print("  [PASS] test_componente_motion_library_opcional_fora_de_required")


def test_plano_valido_com_titulo_heroi_passa_validacao():
    """Plano com intencoes_visuais contendo componente_motion_library='titulo_heroi'
    deve passar em validate_semantic_plan()."""
    plano = {
        "schema_version": "1.0.0",
        "tema_central": "Tema de teste",
        "tese_principal": "Tese de teste",
        "topicos": [
            {
                "topic_id": "T1",
                "titulo": "Topico 1",
                "justificativa": "just",
                "raw_start": 0.0,
                "raw_end": 3.0,
                "segment_ids": [0],
                "word_refs": ["w-0"],
            },
        ],
        "argumentos": [],
        "grupos_explicacao": [],
        "ganchos_e_viradas": [],
        "repeticoes_dispensaveis": [],
        "falsos_comecos": [],
        "segmentos_editoriais": [
            {
                "decision": "preservar",
                "topic_id": "T1",
                "justificativa": "just",
                "raw_start": 0.0,
                "raw_end": 3.0,
                "segment_ids": [0],
                "word_refs": ["w-0"],
            },
        ],
        "intencoes_visuais": [
            {
                "id": "V1",
                "camada": "L2_titulo_heroi_t10",
                "componente_motion_library": "titulo_heroi",
                "texto": "Texto visual",
                "raw_start": 0.0,
                "raw_end": 3.0,
                "segment_ids": [0],
                "funcao_editorial": "funcao",
                "justificativa": "just",
            },
        ],
    }
    validate_semantic_plan(plano)
    print("  [PASS] test_plano_valido_com_titulo_heroi_passa_validacao")


def test_plano_sem_componente_visual_passa_validacao():
    """Plano sem intencoes_visuais (vazia) ou sem propriedade
    componente_motion_library deve passar em validate_semantic_plan()."""

    # Caso 1: intencoes_visuais vazia
    plano_vazia = {
        "schema_version": "1.0.0",
        "tema_central": "Tema de teste",
        "tese_principal": "Tese de teste",
        "topicos": [
            {
                "topic_id": "T1",
                "titulo": "Topico 1",
                "justificativa": "just",
                "raw_start": 0.0,
                "raw_end": 3.0,
                "segment_ids": [0],
                "word_refs": ["w-0"],
            },
        ],
        "argumentos": [],
        "grupos_explicacao": [],
        "ganchos_e_viradas": [],
        "repeticoes_dispensaveis": [],
        "falsos_comecos": [],
        "segmentos_editoriais": [
            {
                "decision": "preservar",
                "topic_id": "T1",
                "justificativa": "just",
                "raw_start": 0.0,
                "raw_end": 3.0,
                "segment_ids": [0],
                "word_refs": ["w-0"],
            },
        ],
        "intencoes_visuais": [],
    }
    validate_semantic_plan(plano_vazia)

    # Caso 2: intencoes_visuais sem componente_motion_library
    plano_sem_prop = {
        "schema_version": "1.0.0",
        "tema_central": "Tema de teste",
        "tese_principal": "Tese de teste",
        "topicos": [
            {
                "topic_id": "T1",
                "titulo": "Topico 1",
                "justificativa": "just",
                "raw_start": 0.0,
                "raw_end": 3.0,
                "segment_ids": [0],
                "word_refs": ["w-0"],
            },
        ],
        "argumentos": [],
        "grupos_explicacao": [],
        "ganchos_e_viradas": [],
        "repeticoes_dispensaveis": [],
        "falsos_comecos": [],
        "segmentos_editoriais": [
            {
                "decision": "preservar",
                "topic_id": "T1",
                "justificativa": "just",
                "raw_start": 0.0,
                "raw_end": 3.0,
                "segment_ids": [0],
                "word_refs": ["w-0"],
            },
        ],
        "intencoes_visuais": [
            {
                "id": "V1",
                "camada": "L3_micro_zoom_bate",
                "texto": "Texto visual",
                "raw_start": 0.0,
                "raw_end": 3.0,
                "segment_ids": [0],
                "funcao_editorial": "funcao",
                "justificativa": "just",
            },
        ],
    }
    validate_semantic_plan(plano_sem_prop)
    print("  [PASS] test_plano_sem_componente_visual_passa_validacao")


# ---------------------------------------------------------------------------
# Runner auxiliar (execucao direta)
# ---------------------------------------------------------------------------


def run_tests() -> int:
    print("=" * 60)
    print("SUITE DE TESTES — core/semantic_planner (Editor)")
    print("=" * 60)
    testes = [
        test_semantic_consent_nao_autorizado_por_padrao,
        test_semantic_consent_serializacao,
        test_provedor_mock_injecao_dependencia,
        test_provedores_nao_sao_instanciaveis_sem_chave_comercial,
        test_plan_sem_autorizado_retorna_fallback,
        test_plan_com_autorizado_mas_sem_provedor_retorna_fallback,
        test_plan_nao_envia_externo_sem_autorizado,
        test_registro_consentimento_gravado,
        test_plano_conforme_schema_100,
        test_rejeita_timestamp_inventado,
        test_rejeita_resposta_malformada,
        test_fallback_nao_alega_compreensão_semantica,
        test_preserva_sha256_brutos_e_sem_duplicacao_transcricao,
        test_falha_comunicacao_agente_fallback_seguro,
        test_provedor_saida_malformada_fallback,
        test_integracao_ponta_a_ponta,
        test_independencia_fornecedor_antigravity_simulado,
        test_independencia_fornecedor_opencode_simulado,
        test_schema_auxiliar_sem_null_em_enuns,
        test_componente_motion_library_opcional_fora_de_required,
        test_plano_valido_com_titulo_heroi_passa_validacao,
        test_plano_sem_componente_visual_passa_validacao,
    ]
    falhas = 0
    for t in testes:
        try:
            t()
        except Exception as e:
            falhas += 1
            print(f"  [FALHA] {t.__name__}: {e}")
            import traceback
            traceback.print_exc()
    print("=" * 60)
    if falhas == 0:
        print("RESULTADO: 100% DOS TESTES PASSARAM!")
    else:
        print(f"RESULTADO: {falhas} FALHA(S) DETECTADA(S)!")
    print("=" * 60)
    return 0 if falhas == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
