import json
import logging
import pkg_resources

from django.utils.translation import ugettext_lazy
from django.template import Context, Template

from xblock.core import XBlock
from xblock.fields import Boolean, Scope, String, Integer
from xblock.fragment import Fragment
from xblockutils.studio_editable import StudioEditableXBlockMixin

import requests

import math
from datetime import datetime

logger = logging.getLogger(__name__)


@XBlock.needs('settings')
class VideofrontXBlock(StudioEditableXBlockMixin, XBlock):
    """
    Play videos based on a modified videojs player. This XBlock supports
    subtitles and multiple resolutions.
    """

    # Used to load open edx-specific settings
    block_settings_key = 'videofront-xblock'

    has_author_view = True

    display_name = String(
        help=ugettext_lazy("The name students see. This name appears in "
                           "the course ribbon and as a header for the video."),
        display_name=ugettext_lazy("Component Display Name"),
        default=ugettext_lazy("New video"),
        scope=Scope.settings
    )

    video_id = String(
        scope=Scope.settings,
        help=ugettext_lazy('Fill this with the ID of the video found in the video uploads dashboard'),
        default="",
        display_name=ugettext_lazy("Video ID")
    )

    allow_download = Boolean(
        help=ugettext_lazy("Allow students to download this video."),
        display_name=ugettext_lazy("Video download allowed"),
        scope=Scope.settings,
        default=True
    )

    editable_fields = ('display_name', 'video_id', 'allow_download', )

    liked = Boolean(default=False, scope=Scope.user_state)
    disliked = Boolean(default=False, scope=Scope.user_state)
    like_count = Integer(default=0, scope=Scope.user_state_summary)
    dislike_count = Integer(default=0, scope=Scope.user_state_summary)

    vid_reported = Boolean(default=False, scope=Scope.user_state)
    aud_reported = Boolean(default=False, scope=Scope.user_state)
    vid_rep_cnt = Integer(default=0, scope=Scope.user_state_summary)
    aud_rep_cnt = Integer(default=0, scope=Scope.user_state_summary)

    # Analytics data
    user_timeline = String(default="0", scope=Scope.user_state)
    total_timeline = String(default="0", scope=Scope.user_state_summary)
    user_watch_time = Integer(default=0, scope=Scope.user_state)
    total_watch_time = Integer(default=0, scope=Scope.user_state_summary)
    last_watch_date = Integer(default=0, scope=Scope.user_state)
    user_views = Integer(default=0, scope=Scope.user_state)
    total_views = Integer(default=0, scope=Scope.user_state_summary)
    video_downloads = Integer(default=0, scope=Scope.user_state_summary)
    transcript_downloads = Integer(default=0, scope=Scope.user_state_summary)
    most_used_controls = String(default="0,0,0,0,0,0,0,0,0,0,0",scope=Scope.user_state_summary)
    # 0 - play/pause
    # 1 - volume change
    # 2 - rate change
    # 3 - seeking
    # 4 - subtitles
    # 5 - toggle transcript
    # 6 - like/dislike
    # 7 - report
    # 8 - pip
    # 9 - download video
    # 10 - download transcript

    def get_icon_class(self):
        """CSS class to be used in courseware sequence list."""
        return 'video'

    def build_fragment(self):
        # 1) Define context
        final_timeline, final_size = self.calculateTimeline(self.total_timeline.split(","))
        context = {
            'display_name': self.display_name,
            'like_count': self.like_count,
            'dislike_count': self.dislike_count,
            'liked': self.liked,
            'disliked': self.disliked,
            'reported': self.aud_reported or self.vid_reported,
            'aud_rep_cnt': self.aud_rep_cnt,
            'vid_rep_cnt': self.vid_rep_cnt,
            'total_timeline': final_timeline,
            'timeline_bar_width': 60.0/final_size,
            'total_views': self.total_views,
            'most_used_controls': self.calculateMostUsedControls(),
            'user_views': self.user_views,
            'last_watch_date': datetime.utcfromtimestamp(self.last_watch_date).strftime('%d-%m-%Y'),
            'video_downloads_cnt': self.video_downloads,
            'transcript_downloads_cnt':self.transcript_downloads,
        }
        # It is a common mistake to define video ids suffixed with empty spaces
        video_id = None if self.video_id is None else self.video_id.strip()
        context['video'], context['messages'], poster_frames = self.get_video_context(video_id)
        context['video_downloads'] = self.get_video_downloads_context(context['video']) if self.allow_download else []
        context['transcript_downloads'] = self.get_transcript_downloads_context(context['video']) if self.allow_download else []

        # 2) Render template
        template = Template(self.resource_string("public/html/xblock.html"))
        content = template.render(Context(context))

        # 3) Build fragment
        fragment = Fragment()
        fragment.add_content(content)
        fragment.add_css(self.resource_string('public/css/xblock.css'))
        fragment.add_css(self.resource_string('public/css/vendor/videojs-resolution-switcher.css'))
        fragment.add_css(self.resource_string('public/css/vendor/videojs-seek-buttons.css'))
        fragment.add_css(self.resource_string('public/css/vendor/videojs-vtt-thumbnails.css'))
        fragment.add_css_url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css')
        fragment.add_css_url('https://vjs.zencdn.net/7.4.1/video-js.css')
        fragment.add_javascript_url('https://vjs.zencdn.net/7.4.1/video.js')
        fragment.add_javascript(self.resource_string('public/js/xblock.js'))
        fragment.add_javascript(self.resource_string('public/js/vendor/videojs-resolution-switcher.js'))
        fragment.add_javascript(self.resource_string('public/js/vendor/videojs-seek-buttons.min.js'))
        fragment.add_javascript(self.resource_string('public/js/vendor/videojs-vtt-thumbnails.min.js'))
        return fragment, video_id, poster_frames

    def student_view(self, context=None): # pylint: disable=W0613
        fragment, video_id, poster_frames = self.build_fragment()

        fragment.initialize_js('VideofrontXBlock', json_args={
            'course_id': unicode(self.location.course_key) if hasattr(self, 'location') else '',
            'video_id': video_id,
            'poster_frames': poster_frames,
            'avg_watch_time': self.calc_total_watch_time()
        })

        return fragment

    def author_view(self, context=None): # pylint: disable=W0613
        fragment, video_id, poster_frames = self.build_fragment()
        fragment.add_css(self.resource_string('public/css/xblock_author_css.css'))

        fragment.initialize_js('VideofrontXBlock', json_args={
            'course_id': unicode(self.location.course_key) if hasattr(self, 'location') else '',
            'video_id': video_id,
            'poster_frames': poster_frames,
            'avg_watch_time': self.calc_total_watch_time()
        })

        return fragment

    def resource_string(self, path):
        """Handy helper for getting resources from our kit."""
        data = pkg_resources.resource_string(__name__, path)
        return data.decode('utf8')

    @staticmethod
    def workbench_scenarios():
        """Useful for debugging this xblock in the workbench (from xblock-sdk)."""
        # Note that this XBlock is not compatible with the workbench because the workbench lacks requirejs.
        return [
            ("Videofront XBlock",
             """<videofront-xblock/>"""),
        ]

    def get_video_context(self, video_id):
        """
        The return values will be used in the view context.

        Returns:
            video (dict)
            messages (tuple): each message is of the form `(level, content)` where
            `level` is 'error', 'warning', etc. and `content` is the message that
            will be displayed to the user.
        """
        messages = []
        video = {}
        poster_frames = ""
        if not video_id:
            messages.append(('warning', ugettext_lazy("You need to define a valid Videofront video ID.")))
            return video, messages, poster_frames
        settings = self.runtime.service(self, "settings").get_settings_bucket(self)
        api_host = settings.get('HOST')
        api_token = settings.get('TOKEN')
        if not api_host:
            messages.append((
                'warning',
                ugettext_lazy("Undefined Videofront hostname. Contact your platform administrator.")
            ))
            return video, messages, poster_frames
        if not api_token:
            messages.append((
                'warning',
                ugettext_lazy("Undefined Videofront auth token. Contact your platform administrator.")
            ))
            return video, messages, poster_frames


        try:
            # TODO implement a cache to store the server responses: we don't
            # want to make a call to videofront for every video view.
            api_response = requests.get(
                '{}/api/v1/videos/{}/'.format(api_host, video_id),
                headers={'Authorization': 'Token ' + api_token}
            )
        except requests.ConnectionError as e:
            messages.append((
                'error',
                ugettext_lazy("Could not reach Videofront server. Contact your platform administrator")
            ))
            logger.error("Could not connect to Videofront: %s", e)
            return video, messages, poster_frames

        if api_response.status_code >= 400:
            if api_response.status_code == 403:
                messages.append(('error', ugettext_lazy("Authentication error")))
            elif api_response.status_code == 404:
                messages.append(('warning', ugettext_lazy("Incorrect video id")))
            else:
                messages.append(('error', ugettext_lazy("An unknown error has occurred")))
                logger.error("Received error %d: %s", api_response.status_code, api_response.content)
            return video, messages, poster_frames

        # Check processing status is correct
        video = json.loads(api_response.content)
        poster_frames = video['poster_frames']
        processing_status = video['processing']['status']
        if processing_status == 'processing':
            messages.append((
                'info',
                ugettext_lazy("Video is currently being processed ({:.2f}%)").format(video['processing']['progress'])
            ))
        elif processing_status == 'failed':
            messages.append((
                'warning',
                ugettext_lazy("Video processing failed: try again with a different video ID")
            ))

        return video, messages, poster_frames

    def get_video_downloads_context(self, video):
        """
        Args:
            video (dict): object as returned by `get_video_context`
        Returns:
            downloads (list): will be passed to the view context
        """
        download_labels = {
            'HD': 'High (720p)',
            'SD': 'Standard (480p)',
            'LD': 'Mobile (320p)',
        }

        # Sort download links by decreasing bitrates
        video_formats = video.get('formats', [])
        video_formats = video_formats[::-1]
        return [
            {
                'url': source['url'],
                'label': download_labels.get(source['name'], source['name'])
            }
            for source in video_formats
        ]

    def get_transcript_downloads_context(self, video):
        """
        Args:
            video (dict): object as returned by `get_video_context`
        Returns:
            downloads (list): will be passed to the view context
        """

        # Sort download links by decreasing bitrates
        subtitles = video.get('subtitles', [])
        return [
            {
                'url': source['url'],
                'language': source['language']
            }
            for source in subtitles
        ]

    def calculateTimeline(self, total_timeline, count=0):
        t_size = len(total_timeline)
        final_size = 1
        if t_size == 0 or self.total_views < 5:
            return [], final_size
        total_timeline = [float(x) for x in total_timeline]
        n_timeline = []
        usable_factors = []
        offset = 0
        if t_size >= 60:
            while (len(usable_factors) == 0):
                factors = self.calculateFactors(t_size + offset)
                usable_factors = [f for f in factors if t_size/f >= 60 and t_size/f <= 240]
                offset -= 1
            final_factor = min(usable_factors)
            final_size = t_size / final_factor
            for i in range(0, t_size, final_factor):
                temp = 0
                for j in range(0, final_factor):
                    if i >= t_size:
                        break
                    temp += total_timeline[i]
                    i += 1
                n_timeline.append(temp)
        else:
            while (len(usable_factors) == 0):
                factors = self.calculateFactors(t_size + offset)
                usable_factors = [f for f in factors if t_size*f >= 60 and t_size*f <= 240]
                offset -= 1
            final_factor = max(usable_factors)
            final_size = t_size * final_factor
            for t in total_timeline:
                for j in range(0, final_factor):
                    n_timeline.append(t)
        max_h = max(n_timeline)
        if max_h > 0:
            n_timeline = [ int(x/max_h * 10) + 2 for x in n_timeline]
        if t_size >= 60:
            n_timeline = [[i*final_factor, x] for i, x in enumerate(n_timeline)]
        else:
            n_timeline = [[i/final_factor, x] for i, x in enumerate(n_timeline)]
        return n_timeline, final_size

    def calculateFactors(self, num):
        factors = []
        for n in range(1, num/2+1):
            if num % n == 0:
                factors.append(n)
        factors.append(num)
        return factors

    def calculateMostUsedControls(self):
        controls = {
            0: 'Play/Pause', 1: 'Volume Change', 2: 'Playback Rate Change',
            3: 'Seeking', 4: 'Subtitles Toggle', 5: 'Transcript Toggle',
            6: 'Like/Dislike', 7: 'Report', 8: 'Picture in Picture',
            9: 'Video Download', 10: 'Transcript Download'
        }
        most_used = self.most_used_controls.split(",")
        most_used_dict = {}
        for i in range(0, len(most_used)):
            most_used_dict[i] = int(most_used[i])
        final_list = []
        for i in range(0, len(most_used_dict)):
            curr_max_key = max(most_used_dict, key=(lambda key: most_used_dict[key]))
            if most_used_dict[curr_max_key] > 0:
                final_list.append(controls[curr_max_key])
            most_used_dict.pop(curr_max_key)

        return final_list[0:4]

    def calc_total_watch_time(self):
            if self.total_views > 0 :
                return self.total_watch_time / self.total_views
            else:
                return 0

    @XBlock.json_handler
    def like_dislike(self, data, suffix=''): # pylint: disable=unused-argument
        """
        Update the user and global rating in response to user action
        """
        if data['voteType'] not in ('like', 'dislike'):
            log.error('error!')
            return
        
        if data['voteType'] == 'like':
            if self.liked:
                self.like_count -= 1
                self.liked = False
            else:
                self.like_count += 1
                self.liked = True
                if self.disliked:
                    self.dislike_count -= 1
                    self.disliked = False
        elif data['voteType'] == 'dislike':
            if self.disliked:
                self.dislike_count -= 1
                self.disliked = False
            else:
                self.dislike_count += 1
                self.disliked = True
                if self.liked:
                    self.like_count -= 1
                    self.liked = False

        return {
            'likes': self.like_count,
            'dislikes': self.dislike_count,
            'liked': self.liked,
            'disliked': self.disliked,
        }
    
    @XBlock.json_handler
    def report(self, data, suffix=''): # pylint: disable=unused-argument
        """
        Update the user and global report status in response to user action
        """
        if data['voteType'] not in ('audio', 'video'):
            log.error('error!')
            return
        
        if data['voteType'] == 'audio':
            if not self.aud_reported:
                self.aud_rep_cnt += 1
                self.aud_reported = True
        elif data['voteType'] == 'video':
            if not self.vid_reported:
                self.vid_rep_cnt += 1
                self.vid_reported = True

        return {
            'aud_reported': self.aud_reported,
            'vid_reported': self.vid_reported,
        }

    @XBlock.json_handler
    def saveTimeline(self, data, suffix=''): # pylint: disable=unused-argument
        """
        Update the watch data in timeline
        """
        
        timeline = data['timeline']
        old_timeline = self.user_timeline.split(",")
        new_timeline = timeline.split(",")
        total_timeline = self.total_timeline.split(",")
        for i in range(len(old_timeline), len(new_timeline)):
            old_timeline.append("0")
        for i in range(len(total_timeline), len(new_timeline)):
            total_timeline.append("0")
        for i in range(0,len(new_timeline)):
            if int(old_timeline[i]) < int(new_timeline[i]):
                total_timeline[i] = str(int(total_timeline[i]) + int(new_timeline[i]))

        self.user_timeline = timeline
        self.total_timeline = ",".join(total_timeline)

        return

    @XBlock.json_handler
    def saveTotalWatchTime(self, data, suffix=''): # pylint: disable=unused-argument
        """
        Return the watch data in timeline
        """
        
        self.total_views += 1
        self.user_views += 1
        self.total_watch_time += data['watchTime']
        self.user_watch_time = data['watchTime']
        self.last_watch_date = data['watchDate']

    @XBlock.json_handler
    def saveTranscriptDownloaded(self, data, suffix=''): # pylint: disable=unused-argument
        """
        Return the watch data in timeline
        """
        
        self.transcript_downloads += 1

    @XBlock.json_handler
    def saveVideoDownloaded(self, data, suffix=''): # pylint: disable=unused-argument
        """
        Return the watch data in timeline
        """
        
        self.video_downloads += 1

    @XBlock.json_handler
    def saveMostUsedControls(self, data, suffix=''): # pylint: disable=unused-argument
        """
        Return the watch data in timeline
        """
        
        new_used_controls = data['controls'].split(",")
        most_used = self.most_used_controls.split(",")
        for i in range(len(most_used), len(new_used_controls)):
            most_used.append("0")
        for i in range(0, len(new_used_controls)):
            most_used[i] = str(int(most_used[i]) + int(new_used_controls[i]))

        self.most_used_controls = ",".join(most_used)

        return
