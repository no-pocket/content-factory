import copy
import pytest


def plan():
    return {'schema_version':'3.0','source_duration':60,'segments':[
        {'segment_id':'a','source_in':0,'source_out':10,'purpose':'setup'},
        {'segment_id':'b','source_in':30,'source_out':40,'purpose':'payoff'}]}


def test_maps_second_segment_words_to_output():
    from app.assembly import validate_assembly, map_words
    validated = validate_assembly(plan(),60)
    assert validated['segments'][1]['output_start'] == 10
    words = map_words(validated,[{'start':31,'end':32,'text':'payoff'}])
    assert words[0]['start'] == 11 and words[0]['end'] == 12
    assert words[0]['source_start'] == 31
    assert validated['duration'] == 20


def test_rejects_partial_word_and_out_of_source():
    from app.assembly import validate_assembly, map_words
    item = plan()
    item['segments'][1]['source_in'] = 31.5
    validated = validate_assembly(item,60)
    with pytest.raises(ValueError,match='word'):
        map_words(validated,[{'start':31,'end':32,'text':'payoff'}])
    with pytest.raises(ValueError):
        validate_assembly(plan(),35)


@pytest.mark.parametrize('mutation', ['empty','negative','overlap','reverse','drift','too_long'])
def test_rejects_invalid_assemblies(mutation):
    from app.assembly import validate_assembly
    item=plan()
    if mutation=='empty': item['segments']=[]
    elif mutation=='negative': item['segments'][0]['source_out']=-1
    elif mutation=='overlap': item['segments'][1]['source_in']=9
    elif mutation=='reverse': item['segments'].reverse()
    elif mutation=='drift': item['segments'][1]['output_start']=11
    elif mutation=='too_long': item.update(source_duration=200,segments=[{'segment_id':'a','source_in':0,'source_out':150,'purpose':'story'}])
    with pytest.raises(ValueError):
        validate_assembly(item,item['source_duration'])


def test_v2_single_segment_is_unchanged():
    from app.assembly import validate_assembly
    from app.timeline import build_timeline
    timeline=build_timeline({'start':0,'end':20,'text':'GTA VI'},[])
    before=copy.deepcopy(timeline)
    assert validate_assembly(timeline,60) == before
    assert timeline == before
