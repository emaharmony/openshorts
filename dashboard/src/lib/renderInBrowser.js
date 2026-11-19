import { renderMediaOnWeb } from '@remotion/web-renderer';
import { ShortVideo } from '../remotion/compositions/ShortVideo';
import {
    FIXED_CAPTION_MAX_CHARS,
    FIXED_CAPTION_MAX_DURATION_MS,
    FIXED_SUBTITLE_STYLE,
} from '../remotion/lib/types';

/**
 * Renders a Remotion composition directly in the browser using WebCodecs.
 * Returns a blob URL to the rendered MP4.
 *
 * @param {object} params
 * @param {string} params.videoUrl - Source video URL
 * @param {number} params.durationInSeconds - Video duration
 * @param {object|null} params.subtitles - SubtitleConfig
 * @param {object|null} params.hook - HookConfig
 * @param {object|null} params.effects - EffectsConfig
 * @param {function} [params.onProgress] - Progress callback (0-1)
 * @param {AbortSignal} [params.signal] - Abort signal for cancellation
 * @returns {Promise<string>} Blob URL of the rendered MP4
 */
export async function renderInBrowser({
    videoUrl,
    durationInSeconds = 30,
    subtitles = null,
    hook = null,
    effects = null,
    onProgress,
    signal,
}) {
    const fixedSubtitles = {
        captions: [],
        position: 'bottom',
        maxChars: FIXED_CAPTION_MAX_CHARS,
        maxDurationMs: FIXED_CAPTION_MAX_DURATION_MS,
        style: FIXED_SUBTITLE_STYLE,
    };
    const fps = 30;
    const durationInFrames = Math.max(1, Math.round(durationInSeconds * fps));

    const { getBlob } = await renderMediaOnWeb({
        composition: {
            component: ShortVideo,
            durationInFrames,
            fps,
            width: 1080,
            height: 1920,
            id: 'ShortVideo',
            calculateMetadata: null,
        },
        inputProps: {
            videoUrl,
            durationInFrames,
            fps,
            width: 1080,
            height: 1920,
            subtitles: fixedSubtitles,
            hook: null,
            effects: null,
        },
        container: 'mp4',
        videoCodec: 'h264',
        videoBitrate: 'high',
        audioCodec: 'aac',
        onProgress: onProgress
            ? ({ progress }) => onProgress(progress)
            : undefined,
        signal,
    });

    const blob = await getBlob();
    return URL.createObjectURL(blob);
}

/**
 * Triggers a download of a blob URL as an MP4 file.
 */
export function downloadBlobUrl(blobUrl, filename = 'output.mp4') {
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}
