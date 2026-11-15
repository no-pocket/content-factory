import pytest

from app.editorial_edits import prepare_timeline_edit
from app.timeline import build_timeline, validate_timeline


def source_fixture():
    transcript = {'segments': [{
        'start': 0, 'end': 10, 'text': 'This is a clear conclusion.',
        'words': [
            {'start': 1, 'end': 2, 'text': 'This'},
            {'start': 2, 'end': 3, 'text': 'is'},
            {'start': 3, 'end': 4, 'text': 'a'},
            {'start': 4, 'end': 5, 'text': 'clear'},
            {'start': 5, 'end': 6, 'text': 'conclusion.'},
        ],
    }]}
    clip = {'start': 1, 'end': 6, 'text': 'This is a clear conclusion.'}
    clip['timeline'] = build_timeline(
        clip, transcript['segments'], editorial_title='Clear conclusion',
    )
    return {'candidates': [clip], 'settings': {'duration_mode': 'classic', 'min_seconds': 1, 'max_seconds': 60}}, transcript


def test_timeline_edit_changes_title_caption_and_human_confirmed_framing():
    job, transcript = source_fixture()
    changes = {
        'title': 'A clearer title',
        'caption_overrides': [{'source_start': 2, 'source_end': 3, 'text': 'isn’t'}],
        'framing_schedule': [{
            'start': 1, 'end': 2,
            'framing': {'preset': 'face', 'roi': {'x': .2, 'y': .1, 'width': .4, 'height': .6}},
        }],
    }

    result = prepare_timeline_edit(job, 0, transcript, changes)

    assert result['clip']['timeline']['layers']['text'][0]['text'] == 'A clearer title'
    assert result['clip']['timeline']['layers']['text'][0]['origin'] == 'human'
    assert result['clip']['timeline']['layers']['captions'][1]['text'] == 'isn’t'
    assert result['clip']['timeline']['framing_schedule'][0]['framing']['preset'] == 'face'
    validate_timeline(result['clip']['timeline'])
    assert job['candidates'][0]['timeline']['layers']['captions'][1]['text'] == 'is'


def test_trim_preserves_word_boundaries_and_rebuilds_source_anchored_captions():
    job, transcript = source_fixture()

    result = prepare_timeline_edit(job, 0, transcript, {'source_start': 2, 'source_end': 6})

    assert result['clip']['start'] == 2
    assert result['clip']['timeline']['source_range'] == {'start': 2, 'end': 6}
    assert [word['text'] for word in result['clip']['timeline']['layers']['captions']] == ['is', 'a', 'clear', 'conclusion.']


def test_later_trim_preserves_existing_caption_and_framing_edits():
    job, transcript = source_fixture()
    edited = prepare_timeline_edit(job, 0, transcript, {
        'title': 'Human title',
        'caption_overrides': [{'source_start': 2, 'source_end': 3, 'text': 'corrected'}],
        'framing_schedule': [{
            'start': .5, 'end': 2.5,
            'framing': {'preset': 'face', 'roi': {'x': .2, 'y': .1, 'width': .4, 'height': .6}},
        }],
    })['clip']
    job['candidates'][0] = edited

    result = prepare_timeline_edit(job, 0, transcript, {'source_start': 2, 'source_end': 6})
    timeline = result['clip']['timeline']

    assert timeline['layers']['text'][0]['text'] == 'Human title'
    assert timeline['layers']['captions'][0]['text'] == 'corrected'
    assert timeline['framing_schedule'][0]['start'] == 0
    assert timeline['framing_schedule'][0]['end'] == 1.5


def test_trim_rejects_cutting_through_a_source_word():
    job, transcript = source_fixture()

    with pytest.raises(ValueError, match='cuts a source word'):
        prepare_timeline_edit(job, 0, transcript, {'source_start': 2.2})


@pytest.mark.parametrize('changes', [
    {'unknown': True},
    {'caption_overrides': [{'source_start': 2, 'source_end': 3, 'text': 'x', 'path': 'unsafe'}]},
    {'title': '0'},
])
def test_timeline_edit_rejects_invalid_fields_and_titles(changes):
    job, transcript = source_fixture()

    with pytest.raises(ValueError):
        prepare_timeline_edit(job, 0, transcript, changes)


def test_caption_override_must_still_match_a_source_word_after_trim():
    job, transcript = source_fixture()
    stale_caption = {'source_start': 1, 'source_end': 2, 'text': 'Changed'}

    with pytest.raises(ValueError, match='no longer matches'):
        prepare_timeline_edit(job, 0, transcript, {
            'source_start': 2, 'caption_overrides': [stale_caption],
        })


def test_framing_schedule_rejects_overlapping_human_windows():
    job, transcript = source_fixture()
    scene = {'preset': 'web', 'roi': {'x': 0, 'y': 0, 'width': 1, 'height': 1}}

    with pytest.raises(ValueError, match='overlaps'):
        prepare_timeline_edit(job, 0, transcript, {'framing_schedule': [
            {'start': 1, 'end': 3, 'framing': scene},
            {'start': 2, 'end': 4, 'framing': scene},
        ]})
