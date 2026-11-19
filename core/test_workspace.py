#!/usr/bin/env python3
"""
core/test_workspace.py

Suíte de testes unitários para core/workspace.py (Editor).

Valida o modelo Workspace -> Marca (projetos/<marca>/branding/config.json) ->
Episodio (projetos/<marca>/episodios/<episodio>/project.json) usando
fixtures temporárias na estrutura real do legado.

Cenários cobertos:
- Criação de Workspace (workspace.json).
- Cadastro/reconhecimento de duas marcas (dr-gestao, ozon-tech reais).
- Criação de dois episódios na mesma marca (via novo_episodio.py).
- Criação de episódios de marcas diferentes.
- Carregamento e validação de branding/config.json.
- Detecção de identificadores/referências inexistentes ou incompletas.
- Isolamento entre marcas e episódios.
- Bloqueio de gravações / path-traversal fora do Workspace autorizado.
- Resolução de logos/, sons/, vinhetas/, overlays/, scripts/
  dentro de projetos/<marca>/branding/.
- Criação de episódio via novo_episodio.py e leitura/atualização de project.json.
- Testes somente-leitura reconhecendo as marcas reais do repositório.
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

# Garante import do pacote core (raiz Editor).
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.workspace import (  # noqa: E402
    WorkspaceLoader,
    WorkspaceError,
    init_workspace,
    load_workspace,
    register_brand,
    load_brand_profile,
    list_brands,
    create_project,
    load_project,
    list_projects,
    resolve_brand_asset,
    resolve_episodio_asset,
)

# Caminho absoluto da raiz do repositório Editor (somente-leitura para marcas).
REPO_ROOT = Path(__file__).resolve().parent.parent
REPO_PROJETOS = REPO_ROOT / "projetos"
REPO_VORTEX = REPO_ROOT / "vortex-edicao"

REPO_DR_GESTAO_CFG = REPO_PROJETOS / "dr-gestao" / "branding" / "config.json"
REPO_OZON_TECH_CFG = REPO_PROJETOS / "ozon-tech" / "branding" / "config.json"

# Episódios de teste criados e removidos dentro do repo (não apaga/move projetos/).
_TEST_EPISODIOS = [
    (REPO_PROJETOS / "dr-gestao" / "episodios" / "ep-test-ws-tmp"),
]


def _limpar_episodios_teste():
    for ep in _TEST_EPISODIOS:
        shutil.rmtree(ep, ignore_errors=True)


# ---------------------------------------------------------------------------
# Testes de unidade (fixtures temporárias)
# ---------------------------------------------------------------------------


def test_init_workspace_cria_workspace_json():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        ws = init_workspace(root)
        assert ws["schema_version"] == "1.0.0"
        assert str(root) == ws["workspace_root"]
        assert (root / "workspace.json").is_file()
        assert ws["paths"]["projetos_dir"] == "projetos"
        assert ws["paths"]["vortex_dir"] == "vortex-edicao"
        assert ws["custody"]["originals_read_only"] is True
    print("  [PASS] test_init_workspace_cria_workspace_json")


def test_list_brands_reconhece_dr_gestao_e_ozon_tech():
    """Teste somente-leitura reconhecendo as marcas reais do repositório."""
    loader = WorkspaceLoader(REPO_ROOT)
    loader.load_workspace()
    marcas = loader.list_brands()
    ids = {m["marca_id"] for m in marcas}
    assert "dr-gestao" in ids, f"dr-gestao não listada: {ids}"
    assert "ozon-tech" in ids, f"ozon-tech não listada: {ids}"
    print("  [PASS] test_list_brands_reconhece_dr_gestao_e_ozon_tech")


def test_load_brand_profile_dr_gestao_real():
    """Carrega branding/config.json real do dr-gestao (somente-leitura)."""
    loader = WorkspaceLoader(REPO_ROOT)
    loader.load_workspace()
    perfil = loader.load_brand_profile("dr-gestao")
    assert perfil["marca_id"] == "dr-gestao"
    assert perfil["display_name"] == "Dr. Gestão"
    cfg = perfil["config_json"]
    assert "marca" in cfg
    assert "preferencias_edicao" in cfg
    assert cfg["marca"]["fonte"] == "Inter"
    assert "rosto" in cfg
    # Defaults de normalização aplicados quando ausentes.
    rd = cfg["preferencias_edicao"]["render_defaults"]
    assert "master_16x9" in rd
    assert "shorts_9x16" in rd
    assert rd["master_16x9"]["width"] == 1920
    assert rd["master_16x9"]["height"] == 1080
    assert rd["shorts_9x16"]["width"] == 1080
    assert rd["shorts_9x16"]["height"] == 1920
    # Áudio normalizado.
    assert cfg["preferencias_edicao"]["audio"]["jumpcut_gap_threshold_ms"] == 450
    # Safe zones normalizados.
    sz = cfg["visual"]["safe_zones"]
    assert "master_16x9" in sz
    assert "shorts_9x16" in sz
    assert sz["master_16x9"]["lower_third_max_w"] == 1150
    assert sz["shorts_9x16"]["lower_third_y"] == 1480
    print("  [PASS] test_load_brand_profile_dr_gestao_real")


def test_load_brand_profile_ozon_tech_real():
    """Carrega branding/config.json real do ozon-tech (somente-leitura)."""
    loader = WorkspaceLoader(REPO_ROOT)
    loader.load_workspace()
    perfil = loader.load_brand_profile("ozon-tech")
    assert perfil["marca_id"] == "ozon-tech"
    assert perfil["display_name"] == "Ozon Tech"
    cfg = perfil["config_json"]
    assert cfg["marca"]["fonte"] == "Inter"
    assert cfg["rosto"] == [960, 420]
    rd = cfg["preferencias_edicao"]["render_defaults"]
    assert rd["master_16x9"]["width"] == 1920
    print("  [PASS] test_load_brand_profile_ozon_tech_real")


def test_register_brand_reconhece_marca_existente_sem_reconstruir():
    """register_brand reconhece marca existente (dr-gestao) sem reconstruir pastas."""
    loader = WorkspaceLoader(REPO_ROOT)
    loader.load_workspace()
    perfil = loader.register_brand("dr-gestao", "Dr. Gestão")
    assert perfil["marca_id"] == "dr-gestao"
    assert perfil["display_name"] == "Dr. Gestão"
    print("  [PASS] test_register_brand_reconhece_marca_existente_sem_reconstruir")


def test_create_project_episodio_na_mesma_marca():
    """Cria episódio na mesma marca via novo_episodio.py (escrita no repo real, limpa depois)."""
    loader = WorkspaceLoader(REPO_ROOT)
    loader.load_workspace()
    loader.register_brand("dr-gestao", "Dr. Gestão")
    ep = loader.create_project("dr-gestao", "ep-test-ws-tmp")
    assert ep["marca_id"] == "dr-gestao"
    assert ep["episodio_id"] == "ep-test-ws-tmp" or ep["project_id"] == "ep-test-ws-tmp"
    # project.json gravado na raiz do episódio.
    pj = REPO_PROJETOS / "dr-gestao" / "episodios" / "ep-test-ws-tmp" / "project.json"
    assert pj.is_file(), f"project.json não encontrado: {pj}"
    _limpar_episodios_teste()
    print("  [PASS] test_create_project_episodio_na_mesma_marca")


def test_create_project_episodios_marcas_diferentes():
    """Cria episódios em marcas diferentes."""
    loader = WorkspaceLoader(REPO_ROOT)
    loader.load_workspace()
    loader.register_brand("dr-gestao", "Dr. Gestão")
    loader.register_brand("ozon-tech", "Ozon Tech")
    # Limpeza prévia para ser idempotente.
    shutil.rmtree(
        REPO_PROJETOS / "dr-gestao" / "episodios" / "ep-dg-tmp", ignore_errors=True
    )
    shutil.rmtree(
        REPO_PROJETOS / "ozon-tech" / "episodios" / "ep-oz-tmp", ignore_errors=True
    )
    try:
        ep_dg = loader.create_project("dr-gestao", "ep-dg-tmp")
        ep_oz = loader.create_project("ozon-tech", "ep-oz-tmp")
        assert ep_dg["marca_id"] == "dr-gestao"
        assert ep_oz["marca_id"] == "ozon-tech"
    finally:
        shutil.rmtree(
            REPO_PROJETOS / "dr-gestao" / "episodios" / "ep-dg-tmp",
            ignore_errors=True,
        )
        shutil.rmtree(
            REPO_PROJETOS / "ozon-tech" / "episodios" / "ep-oz-tmp",
            ignore_errors=True,
        )
    print("  [PASS] test_create_project_episodios_marcas_diferentes")


def test_create_project_exige_marca_existente():
    """create_project rejeita marca que não existe."""
    loader = WorkspaceLoader(REPO_ROOT)
    loader.load_workspace()
    try:
        loader.create_project("marca-inexistente", "ep-x")
        assert False, "Deveria rejeitar marca inexistente."
    except WorkspaceError:
        pass
    print("  [PASS] test_create_project_exige_marca_existente")


def test_load_project_carrega_e_valida():
    """Carrega project.json do episódio recém-criado."""
    loader = WorkspaceLoader(REPO_ROOT)
    loader.load_workspace()
    loader.register_brand("dr-gestao", "Dr. Gestão")
    loader.create_project("dr-gestao", "ep-load-tmp")
    try:
        proj = loader.load_project("dr-gestao", "ep-load-tmp")
        assert proj["marca_id"] == "dr-gestao"
        assert proj["episodio_id"] == "ep-load-tmp" or proj["project_id"] == "ep-load-tmp"
        assert "current_stage" in proj
        assert "sources" in proj
        assert "artifacts" in proj
        assert "approvals" in proj
    finally:
        _limpar_episodios_teste()
        shutil.rmtree(
            REPO_PROJETOS / "dr-gestao" / "episodios" / "ep-load-tmp",
            ignore_errors=True,
        )
    print("  [PASS] test_load_project_carrega_e_valida")


def test_list_projects_por_marca():
    """Lista episódios filtrados por marca."""
    loader = WorkspaceLoader(REPO_ROOT)
    loader.load_workspace()
    loader.register_brand("dr-gestao", "Dr. Gestão")
    loader.create_project("dr-gestao", "ep-list-tmp")
    try:
        eps = loader.list_projects("dr-gestao")
        ids = {e["episodio_id"] for e in eps}
        assert "ep-list-tmp" in ids
    finally:
        _limpar_episodios_teste()
        shutil.rmtree(
            REPO_PROJETOS / "dr-gestao" / "episodios" / "ep-list-tmp",
            ignore_errors=True,
        )
    print("  [PASS] test_list_projects_por_marca")


def test_resolve_brand_asset_logos_sons_overlays_scripts():
    """Resolução de logos/, sons/, vinhetas/, overlays/ e scripts/ dentro de projetos/<marca>/branding/."""
    loader = WorkspaceLoader(REPO_ROOT)
    loader.load_workspace()
    ws = str(REPO_ROOT)
    # logos
    logo = resolve_brand_asset(ws, "dr-gestao", "logos/Logo-Branco.png")
    assert logo.is_file(), f"logo não encontrado: {logo}"
    assert str(logo).startswith(str((REPO_PROJETOS / "dr-gestao" / "branding").resolve()))
    # sons
    som = resolve_brand_asset(ws, "dr-gestao", "sons/clique.wav")
    assert som.is_file(), f"som não encontrado: {som}"
    # vinhetas
    vinheta = resolve_brand_asset(ws, "dr-gestao", "vinhetas/Intro-Dr-Gestao.mp4")
    assert vinheta.is_file(), f"vinheta não encontrada: {vinheta}"
    # overlays
    overlay = resolve_brand_asset(ws, "dr-gestao", "overlays/hook_vendas.png")
    assert overlay.is_file(), f"overlay não encontrado: {overlay}"
    # scripts
    script = resolve_brand_asset(ws, "dr-gestao", "scripts/cenas.py")
    assert script.is_file(), f"script não encontrado: {script}"
    print("  [PASS] test_resolve_brand_asset_logos_sons_overlays_scripts")


def test_bloqueia_path_traversal_brand_asset():
    """Impede path traversal na resolução de assets de marca."""
    loader = WorkspaceLoader(REPO_ROOT)
    loader.load_workspace()
    ws = str(REPO_ROOT)
    for tentativa in [
        "../../../../etc/passwd",
        "..\\..\\..\\..\\windows\\win.ini",
        "../../../../ozon-tech/branding/config.json",
    ]:
        try:
            resolve_brand_asset(ws, "dr-gestao", tentativa)
            assert False, f"Deveria bloquear path traversal: {tentativa!r}"
        except WorkspaceError:
            pass
    print("  [PASS] test_bloqueia_path_traversal_brand_asset")


def test_bloqueia_path_traversal_episodio_asset():
    """Impede path traversal na resolução de assets de episódio."""
    loader = WorkspaceLoader(REPO_ROOT)
    loader.load_workspace()
    ws = str(REPO_ROOT)
    for tentativa in ["../../../../../etc/passwd", "..\\..\\..\\..\\..\\windows\\win.ini"]:
        try:
            resolve_episodio_asset(
                ws, "dr-gestao", "teste-piloto-parte-02", tentativa
            )
            assert False, f"Deveria bloquear path traversal: {tentativa!r}"
        except WorkspaceError:
            pass
    print("  [PASS] test_bloqueia_path_traversal_episodio_asset")


def test_isolamento_entre_marcas():
    """dr-gestao e ozon-tech são isoladas; nenhuma vaza config da outra."""
    loader = WorkspaceLoader(REPO_ROOT)
    loader.load_workspace()
    dg = loader.load_brand_profile("dr-gestao")
    oz = loader.load_brand_profile("ozon-tech")
    assert dg["marca_id"] != oz["marca_id"]
    assert dg["config_json"]["marca"]["destaque"] != oz["config_json"]["marca"]["destaque"]
    assert dg["display_name"] == "Dr. Gestão"
    assert oz["display_name"] == "Ozon Tech"
    print("  [PASS] test_isolamento_entre_marcas")


def test_marca_inexistente_rejeitada():
    """load_brand_profile rejeita marca inexistente."""
    loader = WorkspaceLoader(REPO_ROOT)
    loader.load_workspace()
    try:
        loader.load_brand_profile("marca-que-nao-existe")
        assert False, "Deveria rejeitar marca inexistente."
    except WorkspaceError:
        pass
    print("  [PASS] test_marca_inexistente_rejeitada")


def test_episodio_inexistente_rejeitado():
    """load_project rejeita episódio inexistente."""
    loader = WorkspaceLoader(REPO_ROOT)
    loader.load_workspace()
    try:
        loader.load_project("dr-gestao", "episodio-que-nao-existe")
        assert False, "Deveria rejeitar episódio inexistente."
    except WorkspaceError:
        pass
    print("  [PASS] test_episodio_inexistente_rejeitado")


def test_gravacao_contida_no_workspace():
    """Todas as escritas (workspace.json) ficam dentro do workspace."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        init_workspace(root)
        ws_path = root / "workspace.json"
        assert ws_path.is_file()
        assert str(ws_path.resolve()).startswith(str(root.resolve()))
    print("  [PASS] test_gravacao_contida_no_workspace")


def test_workspace_chaves_ausentes_rejeitadas():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "workspace.json").write_text(
            json.dumps({"schema_version": "1.0.0"}), encoding="utf-8"
        )
        try:
            load_workspace(root)
            assert False, "Deveria rejeitar workspace.json com chaves ausentes."
        except WorkspaceError:
            pass
    print("  [PASS] test_workspace_chaves_ausentes_rejeitadas")


# ---------------------------------------------------------------------------
# Runner auxiliar (execução direta)
# ---------------------------------------------------------------------------


def run_tests():
    print("=" * 60)
    print("SUÍTE DE TESTES — core/workspace.py (Editor)")
    print("=" * 60)
    testes = [
        test_init_workspace_cria_workspace_json,
        test_list_brands_reconhece_dr_gestao_e_ozon_tech,
        test_load_brand_profile_dr_gestao_real,
        test_load_brand_profile_ozon_tech_real,
        test_register_brand_reconhece_marca_existente_sem_reconstruir,
        test_create_project_episodio_na_mesma_marca,
        test_create_project_episodios_marcas_diferentes,
        test_create_project_exige_marca_existente,
        test_load_project_carrega_e_valida,
        test_list_projects_por_marca,
        test_resolve_brand_asset_logos_sons_overlays_scripts,
        test_bloqueia_path_traversal_brand_asset,
        test_bloqueia_path_traversal_episodio_asset,
        test_isolamento_entre_marcas,
        test_marca_inexistente_rejeitada,
        test_episodio_inexistente_rejeitado,
        test_gravacao_contida_no_workspace,
        test_workspace_chaves_ausentes_rejeitadas,
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
