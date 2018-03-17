from django.contrib import admin
from django.template.defaultfilters import filesizeformat
from django.utils.html import format_html, format_html_join
from django.utils.translation import ugettext_lazy as _

from cabinet.base_admin import FileAdminBase
from cabinet.models import File


def fieldset(*fields):
    return [(None, {'fields': fields})]


@admin.register(File)
class FileAdmin(FileAdminBase):
    list_display = ('admin_thumbnail', 'admin_file_name', 'admin_details')
    list_display_links = ('admin_thumbnail', 'admin_file_name')

    def get_fieldsets(self, request, obj=None):
        if obj and obj.image_file.name:
            return fieldset(
                'folder', 'image_file', '_overwrite', 'caption',
                'image_alt_text', 'copyright',
            )

        elif obj and obj.download_file.name:
            return fieldset(
                'folder', 'download_file', '_overwrite', 'caption',
                'copyright',
            )

        else:
            return [
                (None, {'fields': (
                    'folder', 'caption', 'copyright',
                )}),
                (_('Image'), {'fields': (
                    'image_file', 'image_alt_text',
                )}),
                (_('Download'), {'fields': (
                    'download_file',
                )}),
            ]

    def admin_thumbnail(self, instance):
        if instance.image_file.name:
            try:
                return format_html(
                    '<img src="{}" alt=""/>',
                    instance.image_file.crop['50x50'],
                )
            except Exception:
                return format_html('<span class="broken-image"></span>')
        elif instance.download_file.name:
            return format_html(
                '<span class="download download-{}">{}</span>',
                instance.download_type,
                instance.download_type.upper(),
            )
        return ''
    admin_thumbnail.short_description = ''

    def admin_file_name(self, instance):
        return format_html(
            '{} <small>({})</small>',
            instance.file_name,
            filesizeformat(instance.file_size),
        )
    admin_file_name.short_description = _('file name')

    def admin_details(self, instance):
        details = [
            instance.caption,
            instance.copyright,
        ]
        return format_html(
            '<small>{}</small>',
            format_html_join('<br>', '{}', ((d,) for d in details if d)),
        )
    admin_details.short_description = _('details')
