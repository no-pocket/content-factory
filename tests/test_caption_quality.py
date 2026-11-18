from app.caption_quality import analyze_caption_readability

def test_phrase_timing_reports_fast_text_without_changing_content():
    tl={'duration':4,'caption_style':'phrase_v1','layers':{'captions':[{'start':1,'end':1.4,'text':'Uma frase longa demais para ser lida nesta duração.'}]}}
    result=analyze_caption_readability(tl)
    assert result['warnings'][0]['code']=='caption_fast'
    assert result['warnings'][0]['start']==1
    assert tl['layers']['captions'][0]['text'].startswith('Uma frase')

def test_empty_and_normal_captions_are_not_invented():
    assert analyze_caption_readability({'duration':4,'layers':{'captions':[]}})['warnings']==[]
    result=analyze_caption_readability({'duration':4,'caption_style':'phrase_v1','layers':{'captions':[{'start':1,'end':3,'text':'Olá mundo'}]}})
    assert result['warnings']==[]
