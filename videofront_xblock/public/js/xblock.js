function VideofrontXBlock(runtime, element, args) {
  'use strict';

    console.log("videojs:", videojs);

    // Create player function
    var videoplayer = function (elt) {
      var player = videojs(elt);

      // CSS
      $(player.el()).find(
        ".vjs-subtitles-button .vjs-menu-item"
      ).css("text-transform", "none");

      return player;
    };

    var videoPlayerElement = $(element).find('.videoplayer');
    var transcriptElement = videoPlayerElement.find(".transcript");
    var player = videoplayer(videoPlayerElement.find('video')[0]);

    // Configure transcripts
    player.one('loadedmetadata', function() {
      var tracks = player.textTracks();

      // Change track
      tracks.addEventListener('change', function() {

        var enableTranscript = false;
        for (var t = 0; t < this.length; t++) {
          var track = this[t];
          if (track.mode === 'showing') {
            showTranscript(track);
            enableTranscript = true;
          }
        }
        if (!enableTranscript) {
          disableTranscript();
        }
      });

      // Highlight current cue
      for (var t = 0; t < tracks.length; t++) {
        tracks[t].addEventListener('cuechange', oncuechange);
      }
    });

    var showTranscript = function(track) {
      var cues = track.cues;

      // We need to check whether the track is still the one currently showing.
      if (track.mode !== "showing") {
        return;
      }

      // Cues may not be loaded yet. If not, wait until they are. This is
      // suboptimal, but there is no other event to help us determine whether a
      // track was correctly loaded.
      if (!cues || cues.length === 0) {
        window.setTimeout(function() { showTranscript(track); }, 2);
      }

      var htmlContent = "";
      for (var c = 0; c < cues.length; c++) {
        var cue = cues[c];
        htmlContent += "<span class='cue' begin='" + cue.startTime + "'>&nbsp;-&nbsp;" + cue.text + "</span><br/>\n";
      }

      player.width("61%");
      videoPlayerElement.addClass("transcript-enabled");
      transcriptElement.html(htmlContent);

      // Go to time on cue click
      transcriptElement.find(".cue").click(function() {
          player.currentTime($(this).attr('begin'));
      });
    };

    var disableTranscript = function() {
      videoPlayerElement.removeClass("transcript-enabled");
      player.width("100%");
    };

    var oncuechange = function() {
      transcriptElement.find(".current.cue").removeClass("current");
      var cueElement;
      for (var c = 0; c < this.activeCues.length; c++) {
        cueElement = transcriptElement.find(".cue[begin='" + this.activeCues[c].startTime + "']");
        cueElement.addClass("current");
      }
      if (cueElement) {
        // Scroll to cue
        var newtop = transcriptElement.scrollTop() - transcriptElement.offset().top + cueElement.offset().top;
        transcriptElement.animate({
            scrollTop: newtop
        }, 500);
      }
    };

    // Listen to events
    var logTimeOnEvent = function(eventName, logEventName, currentTimeKey, data) {
      player.on(eventName, function() {
        logTime(logEventName, data, currentTimeKey);
      });
    };
    var logTime = function(logEventName, data, currentTimeKey) {
      data = data || {};
      currentTimeKey = currentTimeKey || 'currentTime';
      data[currentTimeKey] = parseInt(player.currentTime());
      log(logEventName, data);
    };
    var logOnEvent = function(eventName, logEventName, data) {
      data = data || {};
      player.on(eventName, function() {
          log(logEventName, data);
      });
    };
    function log(eventName, data) {
        var logInfo = {
          course_id: args.course_id,
          video_id: args.video_id,
        };
        if (data) {
          $.extend(logInfo, data);
        }
        Logger.log(eventName, logInfo);
    }

    logTimeOnEvent('seeked', 'seek_video', 'new_time');
    logTimeOnEvent('ended', 'stop_video');
    logTimeOnEvent('pause', 'pause_video');
    logTimeOnEvent('play', 'play_video');
    logOnEvent('loadstart', 'load_video');
    log('video_player_ready');
    // Note that we have no show/hide transcript button, so there is nothing to
    // log for these events

    player.on('ratechange', function() {
      logTime('speed_change_video', { newSpeed: player.playbackRate() });
    });

    player.videoJsResolutionSwitcher();

}
