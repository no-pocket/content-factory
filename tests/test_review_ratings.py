import pytest

from app.editorial_ui import render_dimension_rating, render_content_grade
from test_editorial_service_v2 import v2job, review_request
from test_editorial_ui import ui_test_session


class RatingUI:
    def __init__(self, selected):
        self.selected = selected
        self.default = None

    def markdown(self, text, **kwargs):
        assert kwargs.get('help')

    def feedback(self, style, **kwargs):
        assert style == 'stars'
        self.default = kwargs['default']
        return self.selected

    def select_slider(self, label, **kwargs):
        assert kwargs['options'] == [None, 0, 1, 2, 3]
        assert kwargs['format_func'](None) != kwargs['format_func'](0)
        assert kwargs['help']
        self.default = kwargs['value']
        return self.selected


@pytest.mark.parametrize('saved,selected,expected', [(None, None, None), (1, 0, 1), (5, 4, 5), (4, None, None)])
def test_optional_stars_preserve_unset_and_saved_values(saved, selected, expected):
    ui = RatingUI(selected)
    assert render_dimension_rating(ui, 'hook', saved, 'test_') == expected
    assert ui.default == (None if saved is None else saved - 1)


@pytest.mark.parametrize('saved', [None, 0, 1, 2, 3])
def test_content_grade_preserves_explicit_zero_and_saved_values(saved):
    ui = RatingUI(saved)
    assert render_content_grade(ui, saved, 'test_') == saved
    assert ui.default == saved


@pytest.mark.parametrize('grade', [None, 0, 3])
def test_saved_ratings_roundtrip_without_inventing_scores(v2job, grade):
    from app import service, store
    from app.editorial_ui import DIMENSION_LABELS
    dimensions = {key: None for key in DIMENSION_LABELS}
    dimensions.update(hook=1, relevance=5)
    service.review_candidate_v2(v2job['id'], v2job['candidates'][0]['candidate_id'],
        review_request(v2job, dimensions=dimensions, content_grade=grade))
    page = ui_test_session(v2job)
    assert not page.exception
    assert page.select_slider[0].value == grade
    next(button for button in page.button if button.label == 'Aprovar').click().run()
    assert not page.exception and not page.error
    event = store.load(v2job['id'])['feedback_events'][-1]
    assert event['dimensions'] == dimensions
    assert event['content_grade'] == grade


def test_unset_grade_can_be_explicitly_zero(v2job):
    from app import store
    page = ui_test_session(v2job)
    assert page.select_slider[0].value is None
    page.select_slider[0].set_value(0)
    next(button for button in page.button if button.label == 'Aprovar').click().run()
    assert not page.exception and not page.error
    event = store.load(v2job['id'])['feedback_events'][-1]
    assert event['content_grade'] == 0
    assert all(value is None for value in event['dimensions'].values())
