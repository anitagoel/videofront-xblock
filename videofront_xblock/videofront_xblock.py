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
    
    def get_icon_class(self):
        """CSS class to be used in courseware sequence list."""
        return 'video'

    def build_fragment(self):
        # 1) Define context
        context = {
            'display_name': self.display_name,
            'like_count': self.like_count,
            'dislike_count': self.dislike_count,
            'liked': self.liked,
            'disliked': self.disliked,
            'reported': self.aud_reported or self.vid_reported,
            'aud_rep_cnt': self.aud_rep_cnt,
            'vid_rep_cnt': self.vid_rep_cnt,
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
        })

        return fragment

    def author_view(self, context=None): # pylint: disable=W0613
        fragment, video_id, poster_frames = self.build_fragment()
        fragment.add_css(self.resource_string('public/css/xblock_author_css.css'))

        fragment.initialize_js('VideofrontXBlock', json_args={
            'course_id': unicode(self.location.course_key) if hasattr(self, 'location') else '',
            'video_id': video_id,
            'poster_frames': poster_frames,
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