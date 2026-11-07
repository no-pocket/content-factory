from app.ui_settings import render_settings_controls
from app.job_settings import DEFAULTS


def test_settings_controls_expose_each_processing_option():
    shown = []
    class FakeStreamlit:
        def text_input(self, label, **kwargs):
            shown.append(kwargs['key'])
            return kwargs['value']
        def number_input(self, label, **kwargs):
            shown.append(kwargs['key'])
            return kwargs['value']
        def selectbox(self, label, options, **kwargs):
            shown.append(kwargs['key'])
            return options[kwargs['index']]
    values = render_settings_controls(FakeStreamlit())
    assert values == DEFAULTS
    assert set(shown) == set(DEFAULTS)


def test_gpu_choice_has_readable_label():
    seen = {}
    class FakeStreamlit:
        def text_input(self, label, **kwargs):
            return kwargs['value']
        def number_input(self, label, **kwargs):
            return kwargs['value']
        def selectbox(self, label, options, **kwargs):
            if kwargs['key'] == 'llm_backend':
                seen['gpu'] = kwargs['format_func']('kepler_gpu')
                seen['cpu'] = kwargs['format_func']('ollama')
            return options[kwargs['index']]
    render_settings_controls(FakeStreamlit())
    assert 'GPU K4200' in seen['gpu']
    assert 'CPU' in seen['cpu']
