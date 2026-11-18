"""Advisory cut-boundary evidence. Never modifies a candidate or source."""
from __future__ import annotations
import math

def suggest_word_boundary(original, words, *, source_duration, max_shift=0.5):
    if any(type(x) not in (int,float) or not math.isfinite(x) for x in (original,source_duration,max_shift)) or not 0 <= original <= source_duration or not 0 < max_shift <= 2:
        raise ValueError('Invalid boundary limits')
    result={'version':1,'original_seconds':original,'suggested_seconds':original,'shift_seconds':0,
            'method':None,'confidence':'unavailable','window_seconds':[max(0,original-max_shift),min(source_duration,original+max_shift)],'reason':'unreliable_word_timing'}
    if not isinstance(words,list) or len(words)<2:
        return result
    intervals=[]
    for w in words:
        if not isinstance(w,dict): return result
        a,b=w.get('start'),w.get('end')
        if any(type(x) not in (int,float) or not math.isfinite(x) for x in (a,b)) or not 0<=a<b<=source_duration:
            return result
        if intervals and a<intervals[-1][1]: return result
        intervals.append((a,b))
    gaps=[(a[1]+b[0])/2 for a,b in zip(intervals,intervals[1:]) if b[0]-a[1]>=0.04]
    if not gaps:
        result['reason']='no_reliable_gap';return result
    suggested=min(gaps,key=lambda t:abs(t-original))
    if abs(suggested-original)>max_shift:
        result['reason']='no_nearby_gap';return result
    result.update(suggested_seconds=round(suggested,3),shift_seconds=round(suggested-original,3),method='word_gap',confidence='advisory',reason='nearby_word_gap')
    return result

def suggest_audio_boundary(original, samples, *, window_start, source_duration, sample_rate):
    """Locate a local energy valley; it is evidence, not proof of a word boundary."""
    if type(sample_rate) is not int or sample_rate < 100 or not isinstance(samples,list):
        raise ValueError('Invalid audio samples')
    end=min(source_duration,window_start+len(samples)/sample_rate)
    result={'version':1,'original_seconds':original,'suggested_seconds':original,'shift_seconds':0,
            'method':None,'confidence':'unavailable','window_seconds':[window_start,end],'reason':'audio_valley_unavailable'}
    if not samples or not 0<=window_start<=original<=end<=source_duration:
        return result
    if any(type(x) not in (float,int) or not math.isfinite(x) for x in samples):
        return result
    hop=max(1,sample_rate//100)
    windows=[(i,math.sqrt(sum(x*x for x in samples[i:i+hop])/len(samples[i:i+hop]))) for i in range(0,len(samples),hop)]
    peak=max(level for _,level in windows)
    if peak<.02:
        result['reason']='audio_too_quiet';return result
    threshold=min(peak*.15,.02)
    valleys=[window_start+(i+hop/2)/sample_rate for i,level in windows if level<=threshold]
    if not valleys: return result
    point=min(valleys,key=lambda x:abs(x-original))
    result.update(suggested_seconds=round(point,3),shift_seconds=round(point-original,3),method='audio_valley',confidence='advisory',reason='local_energy_valley')
    return result


def extract_audio_boundary(source, original, *, source_duration, max_shift=.5, timeout=15):
    import array, subprocess, sys
    start=max(0,original-max_shift); end=min(source_duration,original+max_shift)
    try:
        raw=subprocess.run(['ffmpeg','-v','error','-nostdin','-ss',str(start),'-i',str(source),'-t',str(end-start),
                            '-vn','-ac','1','-ar','16000','-f','s16le','pipe:1'],capture_output=True,check=True,timeout=timeout).stdout
        pcm=array.array('h');pcm.frombytes(raw)
        if sys.byteorder!='little':pcm.byteswap()
        return suggest_audio_boundary(original,[x/32768 for x in pcm],window_start=start,source_duration=source_duration,sample_rate=16000)
    except (OSError,ValueError,subprocess.SubprocessError):
        return {'version':1,'original_seconds':original,'suggested_seconds':original,'shift_seconds':0,'method':None,
                'confidence':'unavailable','window_seconds':[start,end],'reason':'audio_analysis_unavailable'}
