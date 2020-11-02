var video = document.getElementById('video');
var videoSrc = '/video/playlist.m3u8';
if (Hls.isSupported()) {
var hls = new Hls();
hls.loadSource(videoSrc);
hls.attachMedia(video);
hls.on(Hls.Events.MANIFEST_PARSED, function() {
  video.play();
});
}
else if (video.canPlayType('application/vnd.apple.mpegurl')) {
video.src = videoSrc;
video.addEventListener('loadedmetadata', function() {
  video.play();
});
}