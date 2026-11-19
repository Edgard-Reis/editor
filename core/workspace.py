"""
core/workspace.py

Núcleo de configuração do Drifit Editor (Editor), adaptado à estrutura
canônica do legado:

  Workspace -> Marca (projetos/<marca>/branding/config.json) -> Episodio
  (projetos/<marca>/episodios/<episodio>/project.json)

100% agnóstico a marca e episódio. Não altera D:\Drifit\Editor, Editor legado ou
D:\Drifit\Editor. Não integra ingest, transcrição, AI Adapter nem renderização.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Exceções
# ---------------------------------------------------------------------------


class WorkspaceError(Exception):
    """Erro de carregamento/validação/operação do workspace."""


# ---------------------------------------------------------------------------
# Helpers de validação e segurança
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _require_keys(data: Dict[str, Any], keys: List[str], source: str) -> None:
    missing = [k for k in keys if k not in data]
    if missing:
        raise WorkspaceError(f"[{source}] chaves obrigatórias ausentes: {missing}")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_slug(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise WorkspaceError(f"{field_name} não pode ser vazio.")
    if not _SLUG_RE.match(value):
        raise WorkspaceError(
            f"{field_name} inválido '{value}': use apenas [a-z0-9]+(-[a-z0-9]+)*."
        )
    return value


def _resolve_within(workspace_root: Path, *parts: str) -> Path:
    """
    Resolve um caminho dentro de workspace_root, impedindo path traversal.
    Retorna o caminho absoluto (não necessariamente existente).
    """
    base = workspace_root.resolve()
    target = (base / Path(*parts)).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise WorkspaceError(
            f"Caminho fora do workspace autorizado: {'/'.join(parts)}"
        ) from exc
    return target


def _write_json_abs(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _read_json(path: Path, source: str) -> Any:
    if not path.is_file():
        raise WorkspaceError(f"{source} não encontrado: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise WorkspaceError(f"{source} não é JSON válido: {path} ({exc})") from exc


# ---------------------------------------------------------------------------
# Defaults de normalização (herdados dos defaults de render 16:9/9:16, áudio e
# safe_zones do brand_profile.json anterior — preservados como fallback quando
# o branding/config.json não declara explicitamente).
# ---------------------------------------------------------------------------

RENDER_DEFAULTS_16X9 = {
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "scale_filter": "lanczos",
    "target_lufs": -14.0,
    "max_tp_db": -1.0,
}
RENDER_DEFAULTS_9X16 = {
    "width": 1080,
    "height": 1920,
    "fps": 30,
    "target_lufs": -14.0,
    "max_tp_db": -1.0,
}
AUDIO_DEFAULTS = {
    "clean_profile": "vehicular_clean",
    "hpf_hz": 80,
    "silence_guard_ms": [180, 220],
    "jumpcut_gap_threshold_ms": 450,
    "jumpcut_target_gap_ms": [200, 250],
}
SAFE_ZONES_16X9 = {
    "lower_third_max_w": 1150,
    "card_left": [100, 320],
    "card_right": [1220, 320],
    "avoid_face_overlap": True,
}
SAFE_ZONES_9X16 = {
    "t10_y_range": [240, 340],
    "face_y_range": [400, 980],
    "subtitle_y_range": [1226, 1274],
    "lower_third_y": 1480,
}


# ---------------------------------------------------------------------------
# WorkspaceLoader
# ---------------------------------------------------------------------------


class WorkspaceLoader:
    """
    Carrega e valida o modelo Workspace -> Marca -> Episodio, adaptado ao
    legado:

      Workspace (workspace.json)
        -> Marca: projetos/<marca>/branding/config.json (+ PREFERENCIAS.md,
          logos/, vinhetas/, sons/, overlays/, scripts/)
        -> Episodio: projetos/<marca>/episodios/<episodio>/project.json
    """

    def __init__(self, workspace_root: str | Path) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.workspace: Dict[str, Any] = {}
        self._marcas_cache: Dict[str, Dict[str, Any]] = {}
        self._episodios_cache: Dict[str, Dict[str, Any]] = {}

    # -- workspace ----------------------------------------------------------

    def projetos_dir(self) -> Path:
        return _resolve_within(
            self.workspace_root,
            self.workspace.get("paths", {}).get("projetos_dir", "projetos"),
        )

    def vortex_dir(self) -> Path:
        return _resolve_within(
            self.workspace_root,
            self.workspace.get("paths", {}).get("vortex_dir", "vortex-edicao"),
        )

    def load_workspace(self, workspace_path: str | Path | None = None) -> Dict[str, Any]:
        """Carrega e valida workspace.json."""
        path = Path(workspace_path) if workspace_path else self.workspace_root / "workspace.json"
        if not path.is_file():
            raise WorkspaceError(f"workspace.json não encontrado: {path}")
        with open(path, "r", encoding="utf-8") as f:
            self.workspace = json.load(f)

        _require_keys(
            self.workspace,
            ["schema_version", "workspace_root", "paths", "custody"],
            "workspace.json",
        )
        _require_keys(
            self.workspace["custody"],
            ["originals_read_only", "versioned_outputs", "require_all_inputs_in_manifest", "frame_tolerance"],
            "workspace.json.custody",
        )
        _require_keys(
            self.workspace["paths"],
            ["projetos_dir", "vortex_dir"],
            "workspace.json.paths",
        )

        # Limpa caches após recarregar workspace.
        self._marcas_cache = {}
        self._episodios_cache = {}
        return self.workspace

    def init_workspace(
        self,
        workspace_root: str | Path,
        projetos_dir: str = "projetos",
        vortex_dir: str = "vortex-edicao",
        custody: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Cria/valida o workspace.json na raiz do workspace_root."""
        root = Path(workspace_root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        workspace_file = root / "workspace.json"

        if workspace_file.is_file():
            loader = WorkspaceLoader(root)
            return loader.load_workspace()

        workspace_data: Dict[str, Any] = {
            "schema_version": "1.0.0",
            "workspace_root": str(root),
            "paths": {"projetos_dir": projetos_dir, "vortex_dir": vortex_dir},
            "custody": {
                "originals_read_only": True,
                "versioned_outputs": True,
                "require_all_inputs_in_manifest": True,
                "frame_tolerance": 1,
                **(custody or {}),
            },
            "created_at": _iso_now(),
            "updated_at": _iso_now(),
        }
        _write_json_abs(workspace_file, workspace_data)

        loader = WorkspaceLoader(root)
        loader.load_workspace()
        return loader.workspace

    # -- marca --------------------------------------------------------------

    def marca_dir(self, marca_id: str) -> Path:
        """Retorna o diretório da marca: projetos/<marca>/."""
        self.load_workspace()
        _validate_slug(marca_id, "marca_id")
        return _resolve_within(self.workspace_root, "projetos", marca_id)

    def branding_dir(self, marca_id: str) -> Path:
        """Retorna o diretório de branding da marca: projetos/<marca>/branding/."""
        return self.marca_dir(marca_id) / "branding"

    def _branding_config_path(self, marca_id: str) -> Path:
        return self.branding_dir(marca_id) / "config.json"

    def list_brands(self) -> List[Dict[str, Any]]:
        """Lista marcas existentes em projetos/*/branding/."""
        self.load_workspace()
        projetos_root = self.projetos_dir()
        marcas: List[Dict[str, Any]] = []
        if not projetos_root.is_dir():
            return marcas
        for entrada in sorted(projetos_root.iterdir()):
            if not entrada.is_dir():
                continue
            cfg = entrada / "branding" / "config.json"
            if cfg.is_file():
                try:
                    cfg_data = _read_json(cfg, f"branding/config.json[{entrada.name}]")
                    display_name = (
                        cfg_data.get("preferencias_edicao", {}).get("canal")
                        or cfg_data.get("marca", {}).get("destaque")
                        or entrada.name
                    )
                    marcas.append(
                        {
                            "marca_id": entrada.name,
                            "display_name": display_name,
                            "relative_path": f"projetos/{entrada.name}/branding/config.json",
                        }
                    )
                except WorkspaceError:
                    # Marca com config.json inválido: ainda assim listada com slug.
                    marcas.append(
                        {
                            "marca_id": entrada.name,
                            "display_name": entrada.name,
                            "relative_path": f"projetos/{entrada.name}/branding/config.json",
                        }
                    )
        return marcas

    def load_brand_profile(self, marca_id: str) -> Dict[str, Any]:
        """
        Carrega e normaliza config.json da marca em memória. Não mantém duas
        fontes: config.json é a fonte canônica.
        """
        self.load_workspace()
        if marca_id in self._marcas_cache:
            return self._marcas_cache[marca_id]

        _validate_slug(marca_id, "marca_id")
        cfg_path = self._branding_config_path(marca_id)
        if not cfg_path.is_file():
            raise WorkspaceError(
                f"Marca não encontrada: projetos/{marca_id}/branding/config.json"
            )

        cfg = _read_json(cfg_path, f"branding/config.json[{marca_id}]")
        _require_keys(cfg, ["marca", "preferencias_edicao"], f"branding/config.json[{marca_id}]")

        # Normaliza: mescla defaults de render/áudio/safe_zones quando ausentes.
        preferencias = cfg.get("preferencias_edicao", {})
        render_defaults = preferencias.get("render_defaults", {})
        if "master_16x9" not in render_defaults:
            render_defaults["master_16x9"] = dict(RENDER_DEFAULTS_16X9)
        if "shorts_9x16" not in render_defaults:
            render_defaults["shorts_9x16"] = dict(RENDER_DEFAULTS_9X16)
        preferencias["render_defaults"] = render_defaults

        audio = preferencias.get("audio", {})
        for k, v in AUDIO_DEFAULTS.items():
            audio.setdefault(k, v)
        preferencias["audio"] = audio

        visual = cfg.get("visual", {})
        safe_zones = visual.get("safe_zones", {})
        if "master_16x9" not in safe_zones:
            safe_zones["master_16x9"] = dict(SAFE_ZONES_16X9)
        if "shorts_9x16" not in safe_zones:
            safe_zones["shorts_9x16"] = dict(SAFE_ZONES_9X16)
        visual["safe_zones"] = safe_zones

        # Normaliza tokens visuais a partir do bloco legado "marca" quando o
        # config.json nao declara "visual.palette"/"visual.font_family".
        marca_cfg = cfg.get("marca", {}) or {}
        palette = visual.get("palette") or {}
        if not isinstance(palette, dict) or not palette:
            palette = {
                k: v
                for k, v in {
                    "primary": marca_cfg.get("destaque"),
                    "secondary": marca_cfg.get("secundaria"),
                    "accent": marca_cfg.get("ciano"),
                }.items()
                if v
            }
        visual["palette"] = palette
        visual.setdefault("font_family", marca_cfg.get("fonte") or "Inter")
        rosto = cfg.get("rosto") or visual.get("face_anchor_1080p") or [980, 420]
        visual.setdefault("face_anchor_1080p", rosto)
        cfg["visual"] = visual

        # Exposta no nivel raiz para consumo direto pelos componentes de
        # motion_library/ (visual, presenter, broll, assets), mantendo
        # config_json e a compatibilidade com o restante do core.
        presenter = {
            "name": preferencias.get("apresentador", ""),
            "credential": preferencias.get("credencial_oficial", ""),
            "face_anchor_1080p": visual.get("face_anchor_1080p", rosto),
        }
        perfil = {
            "marca_id": marca_id,
            "display_name": preferencias.get("canal", marca_id),
            "apresentador": preferencias.get("apresentador", ""),
            "credencial": preferencias.get("credencial_oficial", ""),
            "config_json": cfg,
            "visual": visual,
            "presenter": presenter,
            "broll": cfg.get("broll", {}) or {},
            "assets": cfg.get("assets", {}) or {},
            "render_defaults": render_defaults,
            "audio": audio,
            "relative_path": f"projetos/{marca_id}/branding/config.json",
        }
        self._marcas_cache[marca_id] = perfil
        return perfil

    def register_brand(
        self, marca_id: str, nome_exibicao: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cadastra/reconhece uma marca. Reutiliza vortex-edicao/criar_projeto.py
        para novas marcas; reconhece marcas existentes (dr-gestao, ozon-tech)
        sem reconstruir pastas.
        """
        self.load_workspace()
        _validate_slug(marca_id, "marca_id")

        # Marca já existe: reconhece sem reconstruir.
        cfg_path = self._branding_config_path(marca_id)
        if cfg_path.is_file():
            return self.load_brand_profile(marca_id)

        # Nova marca: delega a criação de pastas ao criar_projeto.py do legado.
        criar_projeto = self.vortex_dir() / "criar_projeto.py"
        if not criar_projeto.is_file():
            raise WorkspaceError(
                f"vortex-edicao/criar_projeto.py não encontrado: {criar_projeto}"
            )
        nome = nome_exibicao or marca_id.replace("-", " ").title()
        try:
            subprocess.run(
                [sys.executable, str(criar_projeto), marca_id, nome],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.CalledProcessError as exc:
            raise WorkspaceError(
                f"Falha ao executar criar_projeto.py para '{marca_id}': {exc.stderr}"
            ) from exc

        if not cfg_path.is_file():
            raise WorkspaceError(
                f"criar_projeto.py não gerou branding/config.json para '{marca_id}'"
            )
        return self.load_brand_profile(marca_id)

    # -- episodio -----------------------------------------------------------

    def episodios_dir(self, marca_id: str) -> Path:
        """Retorna o diretório de episódios: projetos/<marca>/episodios/."""
        self.load_workspace()
        _validate_slug(marca_id, "marca_id")
        return self.marca_dir(marca_id) / "episodios"

    def episodio_dir(self, marca_id: str, episodio_id: str) -> Path:
        """Retorna o diretório do episódio: projetos/<marca>/episodios/<episodio>/."""
        self.load_workspace()
        _validate_slug(episodio_id, "episodio_id")
        return self.episodios_dir(marca_id) / episodio_id

    def project_file(self, marca_id: str, episodio_id: str) -> Path:
        """Retorna o caminho do project.json do episódio (raiz do episódio)."""
        return self.episodio_dir(marca_id, episodio_id) / "project.json"

    def list_projects(self, marca_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lista episódios. Se marca_id for informado, lista apenas dela."""
        self.load_workspace()
        projetos_root = self.projetos_dir()
        episodios: List[Dict[str, Any]] = []
        marcas = [marca_id] if marca_id else [m["marca_id"] for m in self.list_brands()]
        for mid in marcas:
            ep_dir = self.episodios_dir(mid)
            if not ep_dir.is_dir():
                continue
            for entrada in sorted(ep_dir.iterdir()):
                if not entrada.is_dir():
                    continue
                pj = self.project_file(mid, entrada.name)
                if pj.is_file():
                    try:
                        dados = _read_json(pj, f"project.json[{mid}/{entrada.name}]")
                        episodios.append(
                            {
                                "marca_id": mid,
                                "episodio_id": entrada.name,
                                "display_name": dados.get("nome", entrada.name),
                                "relative_path": f"projetos/{mid}/episodios/{entrada.name}/project.json",
                            }
                        )
                    except WorkspaceError:
                        episodios.append(
                            {
                                "marca_id": mid,
                                "episodio_id": entrada.name,
                                "display_name": entrada.name,
                                "relative_path": f"projetos/{mid}/episodios/{entrada.name}/project.json",
                            }
                        )
        return episodios

    def create_project(
        self, marca_id: str, episodio_id: str, gravacao: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cria um episódio em projetos/<marca>/episodios/<episodio>/, reutilizando
        vortex-edicao/novo_episodio.py na criação e gravando/lendo project.json
        na raiz do episódio (sem criar projects/<id>/).
        """
        self.load_workspace()
        _validate_slug(marca_id, "marca_id")
        _validate_slug(episodio_id, "episodio_id")

        # Marca deve existir.
        cfg_path = self._branding_config_path(marca_id)
        if not cfg_path.is_file():
            raise WorkspaceError(
                f"Marca '{marca_id}' não encontrada. Cadastre-a primeiro com register_brand()."
            )

        pj = self.project_file(marca_id, episodio_id)
        if pj.is_file():
            raise WorkspaceError(
                f"Episódio já existe: projetos/{marca_id}/episodios/{episodio_id}/project.json"
            )

        novo_episodio = self.vortex_dir() / "novo_episodio.py"
        if not novo_episodio.is_file():
            raise WorkspaceError(
                f"vortex-edicao/novo_episodio.py não encontrado: {novo_episodio}"
            )

        cmd = [sys.executable, str(novo_episodio), marca_id, episodio_id]
        if gravacao:
            cmd.append(gravacao)
        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.CalledProcessError as exc:
            raise WorkspaceError(
                f"Falha ao executar novo_episodio.py para '{marca_id}/{episodio_id}': {exc.stderr}"
            ) from exc

        if not pj.is_file():
            # novo_episodio.py não grava project.json por padrão; cria um mínimo
            # se ainda não existir, para que load_project funcione.
            projeto_dados = {
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
            _write_json_abs(pj, projeto_dados)

        return self.load_project(marca_id, episodio_id)

    def load_project(self, marca_id: str, episodio_id: str) -> Dict[str, Any]:
        """Carrega project.json do episódio (raiz do episódio)."""
        self.load_workspace()
        _validate_slug(marca_id, "marca_id")
        _validate_slug(episodio_id, "episodio_id")
        pj = self.project_file(marca_id, episodio_id)
        projeto = _read_json(pj, f"project.json[{marca_id}/{episodio_id}]")
        if projeto.get("episodio_id") != episodio_id and projeto.get("project_id") != episodio_id:
            raise WorkspaceError(
                f"episodio_id do arquivo ({projeto.get('episodio_id') or projeto.get('project_id')}) "
                f"difere do solicitado ({episodio_id})"
            )
        return projeto

    # -- resolução de caminhos ----------------------------------------------

    def resolve_brand_asset(self, marca_id: str, asset_rel_path: str) -> Path:
        """
        Resolve um asset da marca dentro de projetos/<marca>/branding/.
        Suporta logos/, sons/, vinhetas/, overlays/, scripts/.
        """
        self.load_workspace()
        _validate_slug(marca_id, "marca_id")
        return _resolve_within(
            self.workspace_root, "projetos", marca_id, "branding", asset_rel_path
        )

    def resolve_episodio_asset(self, marca_id: str, episodio_id: str, asset_rel_path: str) -> Path:
        """Resolve um asset dentro do episódio: projetos/<marca>/episodios/<episodio>/<asset>."""
        self.load_workspace()
        _validate_slug(marca_id, "marca_id")
        _validate_slug(episodio_id, "episodio_id")
        return _resolve_within(
            self.workspace_root,
            "projetos",
            marca_id,
            "episodios",
            episodio_id,
            asset_rel_path,
        )


# ---------------------------------------------------------------------------
# Funções de conveniência
# ---------------------------------------------------------------------------


def init_workspace(
    workspace_root: str | Path,
    projetos_dir: str = "projetos",
    vortex_dir: str = "vortex-edicao",
    custody: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    loader = WorkspaceLoader(workspace_root)
    return loader.init_workspace(workspace_root, projetos_dir, vortex_dir, custody)


def load_workspace(workspace_root: str | Path) -> Dict[str, Any]:
    loader = WorkspaceLoader(workspace_root)
    return loader.load_workspace()


def register_brand(
    workspace_root: str | Path, marca_id: str, nome_exibicao: Optional[str] = None
) -> Dict[str, Any]:
    loader = WorkspaceLoader(workspace_root)
    return loader.register_brand(marca_id, nome_exibicao)


def load_brand_profile(workspace_root: str | Path, marca_id: str) -> Dict[str, Any]:
    loader = WorkspaceLoader(workspace_root)
    return loader.load_brand_profile(marca_id)


def list_brands(workspace_root: str | Path) -> List[Dict[str, Any]]:
    loader = WorkspaceLoader(workspace_root)
    return loader.list_brands()


def create_project(
    workspace_root: str | Path,
    marca_id: str,
    episodio_id: str,
    gravacao: Optional[str] = None,
) -> Dict[str, Any]:
    loader = WorkspaceLoader(workspace_root)
    return loader.create_project(marca_id, episodio_id, gravacao)


def load_project(
    workspace_root: str | Path, marca_id: str, episodio_id: str
) -> Dict[str, Any]:
    loader = WorkspaceLoader(workspace_root)
    return loader.load_project(marca_id, episodio_id)


def list_projects(
    workspace_root: str | Path, marca_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    loader = WorkspaceLoader(workspace_root)
    return loader.list_projects(marca_id)


def resolve_brand_asset(
    workspace_root: str | Path, marca_id: str, asset_rel_path: str
) -> Path:
    loader = WorkspaceLoader(workspace_root)
    return loader.resolve_brand_asset(marca_id, asset_rel_path)


def resolve_episodio_asset(
    workspace_root: str | Path,
    marca_id: str,
    episodio_id: str,
    asset_rel_path: str,
) -> Path:
    loader = WorkspaceLoader(workspace_root)
    return loader.resolve_episodio_asset(marca_id, episodio_id, asset_rel_path)

