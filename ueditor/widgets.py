# coding: utf-8
# License: MIT, see LICENSE.txt
"""
ueditor 4 forms widget

This ueditor widget was copied and extended from this code by John D'Agostino:
http://code.djangoproject.com/wiki/CustomWidgetsueditor
"""

from __future__ import unicode_literals
from __future__ import absolute_import
import json
import logging
import os
import sys
from django.conf import settings
from django.contrib.staticfiles import finders
from django.forms import Textarea, Media
from django.utils.encoding import smart_text
from django.utils.safestring import mark_safe
from django.utils.translation import get_language, get_language_bidi
from django.template.loader import render_to_string
from django.urls import reverse
from django.contrib.admin import widgets as admin_widgets
from . import settings as qtue_settings

# __all__ = ['UEditor', 'render_ueditor_init_js']
__all__ = ['UEditor']

logging.basicConfig(format='[%(asctime)s] %(module)s: %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(20)

if sys.version_info[:2] < (3, 0):
    logger.warning(
        'Deprecation warning: Python 2 support will be removed '
        'in future releases of ueditor4-lite!'
    )


def language_file_exists(language_code):
    """
    Check if ueditor has a language file for the specified lang code

    :param language_code: language code
    :type language_code: str
    :return: check result
    :rtype: bool
    """
    filename = '{0}.js'.format(language_code)
    path = os.path.join('UE', 'lang', language_code, filename)
    return finders.find(path) is not None


def get_language_config():
    """
    Creates a language configuration for ueditor4 based on Django project settings

    :return: language- and locale-related parameters for ueditor 4
    :rtype: dict
    """
    language_code = convert_language_code(get_language() or settings.LANGUAGE_CODE)
    if not language_file_exists(language_code):
        language_code = language_code[:2]
        if not language_file_exists(language_code):
            # Fall back to English if Tiny MCE 4 does not have required translation
            language_code = 'en'
    config = {'language': language_code}
    if get_language_bidi():
        config['directionality'] = 'rtl'
    else:
        config['directionality'] = 'ltr'
    if qtue_settings.USE_SPELLCHECKER:
        try:
            from enchant import list_languages
        except ImportError as ex:
            raise ImportError(
                'To use spellchecker you need to install pyenchant first!'
            ).with_traceback(ex.__traceback__)
        enchant_languages = list_languages()
        if settings.DEBUG:
            logger.info('Enchant languages: {0}'.format(enchant_languages))
        lang_names = []
        for lang, name in settings.LANGUAGES:
            lang = convert_language_code(lang)
            if lang not in enchant_languages:
                lang = lang[:2]
            if lang not in enchant_languages:
                logger.error('Missing {0} spellchecker dictionary!'.format(lang))
                continue
            if config.get('spellchecker_language') is None:
                config['spellchecker_language'] = lang
            lang_names.append('{0}={1}'.format(name, lang))
        config['spellchecker_languages'] = ','.join(lang_names)
    return config


def convert_language_code(django_lang):
    """
    Converts Django language codes "ll-cc" into ISO codes "ll_CC" or "ll"

    :param django_lang: Django language code as ll-cc
    :type django_lang: str
    :return: ISO language code as ll_CC
    :rtype: str
    """
    lang_and_country = django_lang.split('-')
    try:
        return '_'.join((lang_and_country[0], lang_and_country[1].upper()))
    except IndexError:
        return lang_and_country[0]


def render_ueditor_init_js(qtue_config, callbacks, id_):
    """
    Renders ueditor.init() JavaScript code

    :param qtue_config: ueditor 4 configuration
    :type qtue_config: dict
    :param callbacks: ueditor callbacks
    :type callbacks: dict
    :param id_: HTML element's ID to which ueditor is attached.
    :type id_: str
    :return: ueditor.init() code
    :rtype: str
    """
    if qtue_settings.USE_FILEBROWSER and 'file_browser_callback' not in callbacks:
        callbacks['file_browser_callback'] = 'djangoFileBrowser'
    if qtue_settings.USE_SPELLCHECKER and 'spellchecker_callback' not in callbacks:
        callbacks['spellchecker_callback'] = 'ueditor4_spellcheck'
    if id_:
        qtue_config['selector'] = qtue_config.get('selector', 'textarea') + '#{0}'.format(id_)
    return render_to_string('ueditor/ueditor_init.js',
                            context={'callbacks': callbacks,
                                     'ueditor_config': json.dumps(qtue_config)[1:-1],
                                     'is_admin_inline': '__prefix__' in id_})


class UEditor(Textarea):
    """
    ueditor 4 widget

    It replaces a textarea form widget with a rich-text WYSIWYG `ueditor 4`_ editor widget.

    :param attrs: General Django widget attributes.
    :type attrs: dict
    :param ue_attrs: Additional configuration parameters for ueditor 4.
        They *amend* the existing configuration.
    :type ue_attrs: dict
    :param profile: ueditor 4 configuration parameters.
        They *replace* the existing configuration.
    :type profile: dict

    .. _ueditor 4: https://www.ueditor.com/
    """

    def __init__(self, attrs=None, ue_attrs=None, profile=None):
        super(UEditor, self).__init__(attrs)
        self.ue_attrs = ue_attrs or {}
        self.profile = {}
        default_profile = profile or qtue_settings.CONFIG.copy()
        self.profile.update(default_profile)

    def build_attrs(self, base_attrs, extra_attrs=None, **kwargs):
        attributes = dict(base_attrs, **kwargs)
        if extra_attrs:
            attributes.update(extra_attrs)
        return attributes

    def render(self, name, value, attrs=None, renderer=None):
        if value is None:
            value = ''
        value = smart_text(value)
        qtue_settings = self.profile.copy()
        qtue_settings.update(self.ue_attrs)
        ue_html = """<script id="{name}" name="{name}" type="text/plain">
                                            </script>
                                            <textarea id="{name}_val" style="display:none;" >{value}</textarea>
                                            <script>
                                            (function ($) {{
                                                var ue = UE.getEditor("{name}",{{zIndex: 100}});
                                                ue.ready(function () {{
                                                    var content_val =$('#{name}_val').val();
                                                    ue.setContent(content_val);
                                                }});
                                            }})(grp.jQuery);
                                            </script>""".format(name=name, value=value)

        return mark_safe(ue_html)

    @property
    def media(self):
        js = [qtue_settings.CONFIG_URL, qtue_settings.JS_URL]
        return Media(js=js)


class AdminUEditor(UEditor, admin_widgets.AdminTextareaWidget):
    """ueditor 4 widget for Django Admin interface"""
    pass
