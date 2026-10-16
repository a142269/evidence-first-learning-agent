# 多模态服务包
from backend.app.services.multimodal.pptx_builder import (
    PPTXBuilder,
    PPTXOutline,
    SlideContent,
    get_pptx_builder,
)
from backend.app.services.multimodal.pptx import (
    SlideDeckBuilder,
    SlideDeckSpec,
    CoverSlide,
    AgendaSlide,
    ConceptSlide,
    ComparisonSlide,
    WorkedExampleSlide,
    CodeSlide,
    CheckpointSlide,
    DeckMeta,
    Asset,
    BloomLevel,
    Theme,
    get_theme,
    list_themes,
    get_slide_deck_builder,
)
from backend.app.services.multimodal.mermaid_renderer import (
    MermaidRenderer,
    get_mermaid_renderer,
)
from backend.app.services.multimodal.mermaid import (
    MermaidStudio,
    MindmapSpec,
    FlowchartSpec,
    SequenceSpec,
    ClassDiagramSpec,
    GraphSpec,
    detect_intent,
    get_mermaid_studio,
)
from backend.app.services.multimodal.code_sandbox import (
    CodeSandbox,
    get_code_sandbox,
)
from backend.app.services.multimodal.tts_xunfei import (
    XunfeiTTSService,
    get_tts_service,
)
