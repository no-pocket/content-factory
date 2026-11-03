import React from 'react';
import { AbsoluteFill, interpolate, Sequence, staticFile, useCurrentFrame } from 'remotion';
import { OffthreadVideo } from 'remotion';

type Word = { start: number; end: number; text: string };
type Banner = { text: string; at: number; duration: number };
type FX = { type: string; at: number; duration: number };
type Broll = { asset_id: string; at: number; duration: number; path: string };
export type Timeline = {
  schema_version: string; duration: number; width: number; height: number; fps: number;
  layers: { video: { path: string }; audio: { from: string }; captions: Word[]; text: Banner[]; effects: FX[]; broll: Broll[] };
};
export type ClipProps = { jobId: string; clipNo: string; timeline: Timeline };

const white = '#fbfbfc';
const yellow = '#f5dc45';

// 3-word captions with timing derived only from actual ASR word-level timestamps.
const groupWords = (words: Word[]): Word[][] => {
  const groups: Word[][] = [];
  let current: Word[] = [];
  for (const word of words) {
    if (current.length && (current.length >= 3 || word.start - current[current.length - 1].end > 0.6 || word.end - current[0].start > 1.6)) {
      groups.push(current); current = [];
    }
    current.push(word);
  }
  if (current.length) groups.push(current);
  return groups;
};

export const VerticalClip: React.FC<ClipProps> = ({ jobId, clipNo, timeline }) => {
  const frame = useCurrentFrame();
  const time = frame / 30;
  const root = `jobs/${jobId}/${clipNo}/`;
  const groups = groupWords(timeline.layers.captions);
  const active = groups.find((g) => g[0].start <= time && time < g[g.length - 1].end + 0.10);
  const effect = timeline.layers.effects.find((e) => e.type === 'punch_zoom' && e.at <= time && time < e.at + e.duration);
  const zoom = effect ? interpolate(time - effect.at, [0, 0.12, effect.duration], [1, 1.13, 1.06], { extrapolateRight: 'clamp' }) : 1;

  return (
    <AbsoluteFill style={{ backgroundColor: '#050608', overflow: 'hidden', fontFamily: 'DejaVu Sans, Arial, sans-serif' }}>
      <AbsoluteFill style={{ transform: `scale(${zoom})` }}>
        <OffthreadVideo src={staticFile(`${root}base.mp4`)} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
      </AbsoluteFill>
      {timeline.layers.broll.map((b, i) => (
        <Sequence key={`b${i}`} from={Math.round(b.at * 30)} durationInFrames={Math.max(1, Math.round(b.duration * 30))}>
          <AbsoluteFill>
            <OffthreadVideo src={staticFile(`${root}${b.path}`)} muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          </AbsoluteFill>
        </Sequence>
      ))}
      {/* High contrast shading behind subtitles, no overlap with UI safe areas */}
      <AbsoluteFill style={{ background: 'linear-gradient(transparent 58%, rgba(0,0,0,.48) 78%, rgba(0,0,0,.18) 100%)', pointerEvents: 'none' }} />
      {timeline.layers.text.map((banner, i) => {
        const start = Math.round(banner.at * 30);
        const duration = Math.max(1, Math.round(banner.duration * 30));
        return (
          <Sequence key={`t${i}`} from={start} durationInFrames={duration}>
            <PopBanner text={banner.text} />
          </Sequence>
        );
      })}
      {active && (
        <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'flex-end', padding: '0 44px 230px', pointerEvents: 'none' }}>
          <div style={{ textAlign: 'center', textTransform: 'uppercase', fontWeight: 950, letterSpacing: -0.8, fontSize: 49, lineHeight: 1.16, textShadow: '0 4px 5px #000, 2px 2px 0 #000, -2px 2px 0 #000' }}>
            {active.map((w, i) => {
              const isCurrent = time >= w.start && time < w.end;
              const pop = isCurrent ? interpolate(time - w.start, [0, .08, .18], [1, 1.17, 1], { extrapolateRight: 'clamp' }) : 1;
              return <span key={`${i}-${w.start}`} style={{ display: 'inline-block', color: isCurrent ? yellow : white, transform: `scale(${pop})`, marginRight: 12 }}>{w.text}</span>;
            })}
          </div>
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};

const PopBanner: React.FC<{ text: string }> = ({ text }) => {
  const frame = useCurrentFrame();
  const scale = interpolate(frame, [0, 4, 8], [0.55, 1.14, 1], { extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill style={{ justifyContent: 'flex-start', alignItems: 'center', paddingTop: 130, pointerEvents: 'none' }}>
      <div style={{ maxWidth: '85%', fontWeight: 950, fontSize: 55, lineHeight: 1.1, padding: '15px 20px', textAlign: 'center', color: '#fff', textTransform: 'uppercase', background: 'rgba(12,16,26,0.74)', borderBottom: '5px solid #f5dc45', borderRadius: 12, transform: `scale(${scale})`, textShadow: '1px 3px #050505' }}>{text}</div>
    </AbsoluteFill>
  );
};
