"""Provider-specific protocol previews. No network client or publish side effect.

Endpoints with angle brackets are unresolved protocol steps, never executable URLs.
Secrets are resolved only by a future explicitly authorized runtime transport.
"""
from __future__ import annotations

PROVIDERS = {
    'instagram': {'label': 'Instagram Reels', 'env': ('META_INSTAGRAM_ACCOUNT_ID', 'META_INSTAGRAM_ACCESS_TOKEN', 'META_GRAPH_VERSION'),
                  'requirements': 'Conta profissional, OAuth Instagram e instagram_business_content_publish; versão Graph suportada. URL HTTPS autorizada do vídeo ainda não provisionada; processamento do container antes de media_publish.'},
    'facebook': {'label': 'Facebook Reels', 'env': ('META_FACEBOOK_PAGE_ID', 'META_FACEBOOK_PAGE_TOKEN', 'META_GRAPH_VERSION'),
                 'requirements': 'Página Facebook e Page token com pages_manage_posts e permissões aplicáveis; upload, processamento e finalização separados.'},
    'youtube': {'label': 'YouTube', 'env': ('YOUTUBE_CHANNEL_ID', 'YOUTUBE_ACCESS_TOKEN'),
                'requirements': 'Projeto Google com YouTube Data API e OAuth youtube.upload do canal. Prévia usa privacyStatus private; quota e verificação da conta/projeto ainda precisam ser verificadas.'},
    'tiktok': {'label': 'TikTok', 'env': ('TIKTOK_OPEN_ID', 'TIKTOK_ACCESS_TOKEN'),
               'requirements': 'OAuth video.publish e Content Posting habilitado; Direct Post exige creator_info, escolha de privacidade/consentimento e limite de duração da conta. Cliente não auditado fica restrito a privado; aprovação do app não garantida.'},
}


def request_plan(provider: str, *, title: str, description: str, size: int) -> dict:
    if provider not in PROVIDERS:
        raise ValueError('Unknown publishing provider')
    def step(method, endpoint, **body):
        return {'method': method, 'endpoint': endpoint, 'body': body}
    if provider == 'instagram':
        steps = [step('POST', 'https://graph.instagram.com/<version>/<ig-user-id>/media', media_type='REELS', video_url='<authorized publicly accessible MP4 URL; not provisioned>', caption=description or title),
                 step('GET', 'https://graph.instagram.com/<version>/<container-id>?fields=status_code'),
                 step('POST', 'https://graph.instagram.com/<version>/<ig-user-id>/media_publish', creation_id='<finished-container-id>')]
    elif provider == 'facebook':
        steps = [step('POST', 'https://graph.facebook.com/<version>/<page-id>/video_reels', upload_phase='start'),
                 step('POST', '<provider-returned-upload-url>', file='<approved MP4 bytes>'),
                 step('GET', 'https://graph.facebook.com/<version>/<video-id>?fields=status'),
                 step('POST', 'https://graph.facebook.com/<version>/<page-id>/video_reels', upload_phase='finish', video_id='<uploaded-video-id>', video_state='DRAFT', description=description, title=title)]
    elif provider == 'youtube':
        steps = [step('POST', 'https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status&notifySubscribers=false', snippet={'title': title, 'description': description}, status={'privacyStatus': 'private'}),
                 step('PUT', '<provider-returned-resumable-location>', file='<approved MP4 bytes>', content_type='video/mp4', content_length=size)]
    else:
        steps = [step('POST', 'https://open.tiktokapis.com/v2/post/publish/video/init/', source_info={'source': 'FILE_UPLOAD', 'video_size': size, 'chunk_size': '<validated chunk size>', 'total_chunk_count': '<validated chunk count>'}, post_info={'title': description or title, 'privacy_level': '<explicit user selection from creator_info>'}),
                 step('PUT', '<provider-returned-upload-url>', file='<approved MP4 chunks>'),
                 step('POST', 'https://open.tiktokapis.com/v2/post/publish/status/fetch/', publish_id='<returned-publish-id>')]
    return {'provider': provider, 'executable': False, 'steps': steps,
            'prerequisites': ['OAuth account authorization not verified', PROVIDERS[provider]['requirements']],
            'before_init': ['POST /v2/post/publish/creator_info/query/; display account, privacy options and duration limit; obtain explicit consent'] if provider == 'tiktok' else []}
