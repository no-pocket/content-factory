import array,json,subprocess
from pathlib import Path

def test_assembly_proof_window_uses_output_clock_and_keeps_audio(tmp_path):
 from app.assembly import render_assembly,validate_assembly
 from app.core import get_duration
 source=tmp_path/'source.mp4';target=tmp_path/'montage.mp4'
 subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=white:size=640x360:rate=30:duration=4,drawbox=x=0:y=0:w=30:h=360:color=red:t=fill','-f','lavfi','-i','sine=frequency=440:duration=4','-c:v','libx264','-c:a','aac','-shortest',str(source)],check=True)
 plan=validate_assembly({'schema_version':'3.0','source_duration':4,'segments':[{'segment_id':'a','source_in':0,'source_out':1,'purpose':'setup'},{'segment_id':'b','source_in':3,'source_out':4,'purpose':'proof'}]},4)
 render_assembly(source,plan,target,framing_schedule=[{'start':1.2,'end':1.8,'framing':{'preset':'web','layout_version':'proof_compact_v2'}}])
 for t,proof in ((.5,False),(1.1,False),(1.5,True),(1.9,False)):
  raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(target),'-frames:v','1','-vf','crop=2:2:10:600,scale=1:1','-f','rawvideo','-pix_fmt','rgb24','-'])
  assert (raw[0]>180 and raw[1]<80) if proof else min(raw)>180
 assert abs(get_duration(target)-2)<=1/30
 raw=subprocess.check_output(['ffmpeg','-v','error','-ss','1.5','-i',str(target),'-t','0.1','-vn','-ac','1','-f','s16le','-'])
 samples=array.array('h',raw)
 assert (sum(v*v for v in samples)/len(samples))**.5>500
