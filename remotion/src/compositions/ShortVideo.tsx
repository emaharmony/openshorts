import React from "react";
import { AbsoluteFill } from "remotion";
import { Video } from "@remotion/media";
import { FIXED_SUBTITLE_STYLE, type ShortVideoProps } from "../lib/types";
import { Subtitles } from "./Subtitles";

/**
 * Main composition that layers all post-processing on top of the base video.
 * Uses @remotion/media Video for browser-side rendering compatibility.
 */
export const ShortVideo: React.FC<Record<string, unknown>> = (rawProps) => {
  const { videoUrl, subtitles } =
    rawProps as unknown as ShortVideoProps;
  const fixedSubtitles = subtitles ? {
    captions: subtitles.captions,
    position: "bottom" as const,
    style: FIXED_SUBTITLE_STYLE,
  } : null;
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* Fill letterbox space with a blurred copy, then preserve the whole
          gameplay/camera frame in the foreground. This cannot crop the baked-in
          OBS camera inset or honor caller zoom/effect transforms. */}
      <Video
        src={videoUrl}
        style={{ width: "100%", height: "100%", objectFit: "cover", filter: "blur(32px) brightness(0.55)", transform: "scale(1.08)" }}
      />
      <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Video
          src={videoUrl}
          style={{ width: "100%", height: "100%", objectFit: "contain" }}
        />
      </div>

      {/* Layer 2: Animated subtitles */}
      {fixedSubtitles && <Subtitles config={fixedSubtitles} />}

    </AbsoluteFill>
  );
};
