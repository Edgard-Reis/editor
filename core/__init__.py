r"""
core — Núcleo de configuração do Drifit Editor (Editor).

Modelo de domínio Workspace -> Brand Profile -> Editing Project, 100% agnóstico
a marca e a edição. Não altera D:\Drifit\Editor nem D:\Drifit\Editor.
"""

from __future__ import annotations

from .workspace import (  # noqa: F401
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

from .ingest import (  # noqa: F401
    IngestError,
    compute_sha256,
    inspect_media_ffprobe,
    check_os_protection,
    extract_speech_audio,
    check_tool,
    ingest_media,
    verify_source_integrity,
)

from .analyze import (  # noqa: F401
    AnalyzeError,
    analyze_episodio,
    analyze_episodio_wrapper,
    PhoneticVerifier,
    build_alignment_from_words,
)

from .briefing import (  # noqa: F401
    BriefingError,
    AnalisadorEditorial,
    MotionProposal,
    RepeticaoFalsaComeco,
    gerar_briefing,
)

from .edl_builder import (  # noqa: F401
    EdlBuilderError,
    build_edl_from_alignment,
    CAMADAS_EDITORIAL,
    r3,
)

from .master_lint import (  # noqa: F401
    MasterLintError,
    lint,
    run_lint,
    run_lint_workspace,
    REQUIRED_LAYERS,
    LAYER_ROLES,
)

from .semantic_plan import (  # noqa: F401
    SemanticPlanError,
    SEMANTIC_PLAN_SCHEMA_VERSION,
    IMPLEMENTED_MOTION_COMPONENTS,
    validate_semantic_plan,
    load_semantic_plan,
)

from .semantic_planner import (  # noqa: F401
    SemanticPlannerError,
    SemanticPlannerProvider,
    SemanticConsent,
    AntigravityCliProvider,
    OpenCodeCliProvider,
    CallableMockProvider,
    plan_episodio_semantics,
    load_semantic_consent,
    is_semantic_consent_authorized,
)

__version__ = "1.0.0"
__all__ = [
    "WorkspaceLoader",
    "WorkspaceError",
    "init_workspace",
    "load_workspace",
    "register_brand",
    "load_brand_profile",
    "list_brands",
    "create_project",
    "load_project",
    "list_projects",
    "resolve_brand_asset",
    "resolve_episodio_asset",
    "IngestError",
    "compute_sha256",
    "inspect_media_ffprobe",
    "check_os_protection",
    "extract_speech_audio",
    "check_tool",
    "ingest_media",
    "verify_source_integrity",
    "AnalyzeError",
    "analyze_episodio",
    "analyze_episodio_wrapper",
    "PhoneticVerifier",
    "build_alignment_from_words",
    "BriefingError",
    "AnalisadorEditorial",
    "MotionProposal",
    "RepeticaoFalsaComeco",
    "gerar_briefing",
    "EdlBuilderError",
    "build_edl_from_alignment",
    "CAMADAS_EDITORIAL",
    "r3",
    "MasterLintError",
    "lint",
    "run_lint",
    "run_lint_workspace",
    "REQUIRED_LAYERS",
    "LAYER_ROLES",
    "SemanticPlanError",
    "SEMANTIC_PLAN_SCHEMA_VERSION",
    "IMPLEMENTED_MOTION_COMPONENTS",
    "validate_semantic_plan",
    "load_semantic_plan",
    "SemanticPlannerError",
    "SemanticPlannerProvider",
    "SemanticConsent",
    "AntigravityCliProvider",
    "OpenCodeCliProvider",
    "CallableMockProvider",
    "plan_episodio_semantics",
    "load_semantic_consent",
    "is_semantic_consent_authorized",
]
