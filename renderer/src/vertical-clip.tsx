import React from 'react';
import { AbsoluteFill, interpolate, Sequence, staticFile, useCurrentFrame } from 'remotion';
import { OffthreadVideo } from 'remotion';

type Word = { start: number; end: number; text: string; segment_id?: string; output_segment_end?: number };
type Banner = { text: string; at: number; duration: number; style?: string };
type FX = { type: string; at: number; duration: number };
type Broll = { asset_id: string; at: number; duration: number; path: string };
type Region = { x: number; y: number; width: number; height: number };
type Framing = { mode: 'contain' | 'cover'; caption_safe_area: Region; title_safe_area: Region };
export type Timeline = {
  schema_version: string; duration: number; width: number; height: number; fps: number;
  framing_resolved?: Framing;
  segments?: { output_start: number; duration: number; frame_count: number; framing_resolved?: Framing }[];
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
    if (current.length && (current.length >= 3 || word.start - current[current.length - 1].end > 0.6 || word.end - current[0].start > 1.6 || word.segment_id !== current[0].segment_id)) {
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
  const active = groups.find((g, index) => g[0].start <= time && time < Math.min(
    g[g.length - 1].end + 0.10, groups[index + 1]?.[0].start ?? Infinity, g[0].output_segment_end ?? Infinity));
  const effect = timeline.layers.effects.find((e) => e.type === 'punch_zoom' && e.at <= time && time < e.at + e.duration);
  const scene = timeline.segments?.find(s => s.output_start <= time && time < s.output_start+s.duration);
  const framing = scene?.framing_resolved ?? timeline.framing_resolved;
  const zoom = effect && !framing ? interpolate(time - effect.at, [0, 0.12, effect.duration], [1, 1.13, 1.06], { extrapolateRight: 'clamp' }) : 1;
  const safe = framing?.caption_safe_area;

  return (
    <AbsoluteFill style={{ backgroundColor: '#050608', overflow: 'hidden', fontFamily: 'DejaVu Sans, Arial, sans-serif' }}>
      <AbsoluteFill style={{ transform: `scale(${zoom})` }}>
        <OffthreadVideo src={staticFile(`${root}base.mp4`)} style={{ width: '100%', height: '100%', objectFit: framing?.mode ?? 'cover' }} />
      </AbsoluteFill>
      {timeline.layers.broll.map((b, i) => (
        <Sequence key={`b${i}`} from={Math.round(b.at * 30)} durationInFrames={Math.max(1, Math.round(b.duration * 30))}>
          <AbsoluteFill>
            <OffthreadVideo src={staticFile(`${root}${b.path}`)} muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          </AbsoluteFill>
        </Sequence>
      ))}
      {/* High contrast shading behind subtitles, no overlap with UI safe areas */}
      <AbsoluteFill style={{ background: framing ? 'none' : 'linear-gradient(transparent 58%, rgba(0,0,0,.48) 78%, rgba(0,0,0,.18) 100%)', pointerEvents: 'none' }} />
      {timeline.layers.text.map((banner, i) => {
        const start = Math.round(banner.at * 30);
        const duration = Math.max(1, Math.round(banner.duration * 30));
        return (
          <Sequence key={`t${i}`} from={start} durationInFrames={duration}>
            <PopBanner text={banner.text} compact={banner.style === 'compact_editorial_v1'} safe={framing?.title_safe_area} />
          </Sequence>
        );
      })}
      {active && (
        <AbsoluteFill style={{ alignItems: 'center', justifyContent: safe ? 'center' : 'flex-end',
          ...(safe ? {left: safe.x * timeline.width, top: safe.y * timeline.height, width: safe.width * timeline.width, height: safe.height * timeline.height} : {padding: '0 44px 230px'}), pointerEvents: 'none' }}>
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

const PopBanner: React.FC<{ text: string; compact: boolean; safe?: Region }> = ({ text, compact, safe }) => {
  const frame = useCurrentFrame();
  const scale = interpolate(frame, [0, 4, 8], [0.55, 1.14, 1], { extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill style={{ justifyContent: 'flex-start', alignItems: 'center', paddingTop: safe ? safe.y * 1280 : compact ? 95 : 130, pointerEvents: 'none' }}>
      <div style={{ maxWidth: compact ? '82%' : '85%', fontWeight: 950, fontSize: compact ? 38 : 55, lineHeight: 1.1, padding: '15px 20px', textAlign: 'center', color: '#fff', textTransform: 'uppercase', background: 'rgba(12,16,26,0.74)', borderBottom: '5px solid #f5dc45', borderRadius: 12, transform: `scale(${scale})`, textShadow: '1px 3px #050505', ...(compact ? {display:'-webkit-box', WebkitBoxOrient:'vertical' as const, WebkitLineClamp:3, overflow:'hidden', overflowWrap:'anywhere' as const} : {}) }}>{text}</div>
    </AbsoluteFill>
  );
};
