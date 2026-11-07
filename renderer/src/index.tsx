import React from 'react';
import { Composition, registerRoot } from 'remotion';
import { VerticalClip, type ClipProps } from './vertical-clip';

const defaultProps: ClipProps = {
  jobId: 'demo', clipNo: '1',
  timeline: {
    schema_version: '2.0', duration: 10, width: 720, height: 1280, fps: 30,
    layers: { video: { path: 'base.mp4' }, audio: { from: 'base.mp4' }, captions: [],
      text: [], effects: [], broll: [] },
  },
};

const Root: React.FC = () => (
  <Composition
    id="VerticalClip"
    component={VerticalClip}
    width={720}
    height={1280}
    fps={30}
    durationInFrames={300}
    defaultProps={defaultProps}
    calculateMetadata={({ props }) => ({ durationInFrames: Math.max(1, props.timeline.schema_version === '3.0'
      ? (props.timeline.segments ?? []).reduce((total, segment) => total + segment.frame_count, 0)
      : Math.ceil(props.timeline.duration * 30)) })}
  />
);
registerRoot(Root);
