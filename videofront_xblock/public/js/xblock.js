function VideofrontXBlock(runtime, element, args) {
    $(window).resize(function () {
      $('#tscript').height($('#video-cont').outerHeight(true));
    });
    avg_watch_time = args.avg_watch_time;
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
    var show_transcript = true;
    var enableTranscript = false;
    var track_showing = player.textTracks()[0];
    $('.transcript-toggle', element).click(function(eventObject) {
      $('.dropdown-content').css("display","none");
      if (show_transcript){
        show_transcript = false;
        disableTranscript();
        $('.transcript-toggle', element).text("Enable Transcript");
      } else {
        show_transcript = true;
        if (enableTranscript)
          showTranscript(track_showing);
        $('.transcript-toggle', element).text("Disable Transcript");
      }
      sendControlsAnalytics("0,0,0,0,0,1,0,0,0,0,0");
    });
    player.one('loadedmetadata', function() {
      var tracks = player.textTracks();

      // Change track
      tracks.addEventListener('change', function() {

        enableTranscript = false;
        for (var t = 0; t < this.length; t++) {
          var track = this[t];
          if (track.mode === 'showing') {
            showTranscript(track);
            track_showing = track;
            enableTranscript = true;
          }
        }
        if (!enableTranscript) {
          disableTranscript();
        }

        sendControlsAnalytics("0,0,0,0,1,0,0,0,0,0,0");
      });

      // Highlight current cue
      for (var t = 0; t < tracks.length; t++) {
        tracks[t].addEventListener('cuechange', oncuechange);
      }
    });

    var showTranscript = function(track) {
      if (!show_transcript)
        return;
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

      videoPlayerElement.addClass("transcript-enabled");
      $('#tscript').height($('#video-cont').outerHeight(true));
      transcriptElement.html(htmlContent);

      // Go to time on cue click
      transcriptElement.find(".cue").click(function() {
          player.currentTime($(this).attr('begin'));
      });
    };

    var disableTranscript = function() {
      videoPlayerElement.removeClass("transcript-enabled");
      $('#tscript').height($('#video-cont').outerHeight(true));
    };

    var oncuechange = function() {
      if (!show_transcript)
        return;
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

    // Restore height of transcript div after exiting full screen
    player.on('fullscreenchange', function() {
      $('#tscript').height($('#video-cont').outerHeight(true));
    });

    // Play video if player visible
    var hasBeenPlayed = false;
    var playVideoIfVisible = function () {
      var hT = $('#video-cont').offset().top,
        hH = $('#video-cont').outerHeight(),
        wH = $(window).height(),
        wS = $(window).scrollTop();
      if (wS+wH >= hT && wS <= (hT+hH)){
        if (!hasBeenPlayed){
          player.play();
          hasBeenPlayed = true;
        }
      }
    };
    player.one('ready', function() {
      hasBeenPlayed = false;
      playVideoIfVisible();
    });
    $(window).scroll(function() {
      playVideoIfVisible();
    });

    player.videoJsResolutionSwitcher();

    player.seekButtons({
      //forward: 30,
      back: 10
    });

    player.vttThumbnails({
      src: args.poster_frames
    });

    // Implement Star Rating
    var handlerUrl = runtime.handlerUrl(element, 'like_dislike');
    function updateLikeDislike(data) {
      if (data.liked)
        $('.fa-thumbs-o-up', element).css("color","green");
      else
        $('.fa-thumbs-o-up', element).css("color","black");
      if (data.disliked)
        $('.fa-thumbs-o-down', element).css("color","red");
      else
        $('.fa-thumbs-o-down', element).css("color","black");
      $('.like-count', element).text(data.likes);
      $('.dislike-count', element).text(data.dislikes);
    }
    $('.like-btn', element).click(function(eventObject) {
      $.ajax({
          type: "POST",
          url: handlerUrl,
          data: JSON.stringify({voteType: 'like'}),
          success: updateLikeDislike
      });
      sendControlsAnalytics("0,0,0,0,0,0,1,0,0,0,0");
    });
    $('.dislike-btn', element).click(function(eventObject) {
      $.ajax({
          type: "POST",
          url: handlerUrl,
          data: JSON.stringify({voteType: 'dislike'}),
          success: updateLikeDislike
      });
      sendControlsAnalytics("0,0,0,0,0,0,1,0,0,0,0");
    });

    // Configure drop down menu
    var menu_visible = false;
    $('.menu-button').click(function(eventObject) {
      if (!menu_visible){
        $('.dropdown-content').css("display","block");
        menu_visible = true;
        eventObject.stopPropagation();
      }
    });
    $('html').click(function() {
      if (menu_visible){
        $('.dropdown-content').css("display","none");
        menu_visible = false;
      }
      if (report_optns_showing) {
        hideReportOpts();
      }
    });

    // Implement report feature
    var report_optns_showing = false;
    function showReportOpts() {
      $('.report-video-q', element).css("display","block");
      $('.report-audio-q', element).css("display","block");
      report_optns_showing = true;
    }
    function hideReportOpts() {
      $('.report-video-q', element).css("display","none");
      $('.report-audio-q', element).css("display","none");
      report_optns_showing = false;
    }
    hideReportOpts(); // Hide options initially
    $('.report-btn', element).click(function(eventObject) {
      if (report_optns_showing){
        hideReportOpts();
      } else {
        showReportOpts();
      }
      eventObject.stopPropagation();
    });
    var reportHandlerUrl = runtime.handlerUrl(element, 'report');
    function updateReportStatus(data) {
      if (data.aud_reported || data.vid_reported) {
        hideReportOpts()
        $('.report-btn', element).text("Report (reported)");
      }
    }
    $('.report-audio-q', element).click(function(eventObject) {
      $.ajax({
        type: "POST",
        url: reportHandlerUrl,
        data: JSON.stringify({voteType: 'audio'}),
        success: updateReportStatus
      });
      sendControlsAnalytics("0,0,0,0,0,0,0,1,0,0,0");
    });
    $('.report-video-q', element).click(function(eventObject) {
      $.ajax({
        type: "POST",
        url: reportHandlerUrl,
        data: JSON.stringify({voteType: 'video'}),
        success: updateReportStatus
      });
      sendControlsAnalytics("0,0,0,0,0,0,0,1,0,0,0");
    });
    $('.analytics_btn', element).click(function(eventObject) {
      $('#analytics_cont').css('display','flex');
    });
  
    // Analytics Server Urls
    getTimelineHandlerUrl = runtime.handlerUrl(element, 'getTimeline');
    saveTimelineHandlerUrl = runtime.handlerUrl(element, 'saveTimeline');
    saveTotalWatchTimeHandlerUrl = runtime.handlerUrl(element, 'saveTotalWatchTime');
    saveMostUsedControlsHandlerUrl = runtime.handlerUrl(element, 'saveMostUsedControls');
    saveTranscriptDownloadedHandlerUrl = runtime.handlerUrl(element, 'saveTranscriptDownloaded');
    saveVideoDownloadedHandlerUrl = runtime.handlerUrl(element, 'saveVideoDownloaded');

    $('#avg_watch_time').text(secondsToString(avg_watch_time));
}