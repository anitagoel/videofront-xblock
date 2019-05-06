# Videofront XBlock

This is an [Open edX XBlock](https://xblock.readthedocs.io/en/latest/) for playing videos stored on a [Videofront](https://github.com/anitagoel/videofront/) instance.

This XBlock was heavily inspired by the [regisb Videofront XBlock](https://github.com/regisb/videofront-xblock).

Note that this XBlock is not compatible with the workbench because the workbench lacks requirejs.

Use the [edx Platform](https://github.com/edx/devstack) instead.

## Install
SSH into the 'studio' docker container and install

    pip install -e git+https://github.com/anitagoel/videofront-xblock.git@master#egg=videofront-xblock

Add the xblock to your advanced modules in the Studio:

![Studio advanced settings](./config.png?raw=true) 

## Configuration

Set the following values in your Open edX settings:

    XBLOCK_SETTINGS['videofront-xblock'] = {
        'HOST': 'http://yourvideofront.com',
        'TOKEN': 'addyourvideofrontapitokenhere',
    }

## License

The code in this repository is licensed the Apache 2.0 license unless otherwise noted.

Please see `LICENSE` for details.
