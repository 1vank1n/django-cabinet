from django import forms
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.admin.options import IncorrectLookupParameters
from django.contrib.admin.utils import get_deleted_objects
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import router, transaction
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.defaultfilters import filesizeformat
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _

from cabinet.models import Folder, File


class FolderListFilter(admin.RelatedFieldListFilter):
    def queryset(self, request, queryset):
        if self.used_parameters:
            try:
                return queryset.filter(**self.used_parameters)
            except ValidationError as e:
                raise IncorrectLookupParameters(e)
        elif request.GET:
            return queryset
        else:
            return queryset.filter(folder__isnull=True)


class FolderForm(forms.ModelForm):
    class Meta:
        model = Folder
        fields = ('parent', 'name')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['delete'] = forms.BooleanField(
                required=False,
                label=_('Delete this folder'),
            )


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = (
        'admin_thumbnail',
        'admin_file_name',
        'admin_details',
    )
    list_display_links = (
        'admin_file_name',
    )
    list_filter = (
        ('folder', FolderListFilter),
    )
    search_fields = (
        'file_name',
    )

    fieldsets = [
        (None, {
            'fields': ('folder',),
        }),
        (_('Image'), {
            'fields': ('image_file',),
        }),
        (_('Download'), {
            'fields': ('download_file',),
        }),
    ]

    def get_urls(self):
        from django.conf.urls import url

        return [
            url(
                r'^folder/add/$',
                self.admin_site.admin_view(self.folder_add),
                name='cabinet_folder_add',
            ),
            url(
                r'^folder/(.+)/$',
                self.admin_site.admin_view(self.folder_change),
                name='cabinet_folder_change',
            ),
        ] + super().get_urls()

    def changelist_view(self, request):
        cabinet_context = {}
        folder = None

        folder__id__exact = request.GET.get('folder__id__exact')
        q = request.GET.get('q')
        if not q:
            if folder__id__exact:
                try:
                    folder = Folder.objects.get(pk=folder__id__exact)
                except Folder.DoesNotExist:
                    return HttpResponseRedirect('?e=1')

            if folder is None:
                cabinet_context.update({
                    'folder': None,
                    'folder_children': Folder.objects.filter(
                        parent__isnull=True,
                    ).annotate(
                        num_subfolders=Count('children'),
                        num_files=Count('files'),
                    ),
                })
            else:
                cabinet_context.update({
                    'folder': folder,
                    'folder_children': folder.children.annotate(
                        num_subfolders=Count('children'),
                        num_files=Count('files'),
                    ),
                })

        return super().changelist_view(request, extra_context={
            'cabinet': cabinet_context,
            'title': folder or _('Root folder'),
        })

    def folder_add(self, request):
        with transaction.atomic(using=router.db_for_write(self.model)):
            return self._folder_form(
                request,
                {
                    'initial': {
                        'parent': request.GET.get('parent'),
                    },
                },
            )

    def folder_change(self, request, object_id):
        with transaction.atomic(using=router.db_for_write(self.model)):
            return self._folder_form(
                request,
                {
                    'instance': get_object_or_404(Folder, pk=object_id),
                },
            )

    def _folder_form(self, request, kw):
        info = self.model._meta.app_label, self.model._meta.model_name
        original = kw.get('instance')
        add = not original

        if add:
            if not self.has_add_permission(request):
                raise PermissionDenied
        else:
            if not self.has_change_permission(request, original):
                raise PermissionDenied

        if request.method == 'POST':
            form = FolderForm(request.POST, **kw)
            if form.is_valid():
                if original and form.cleaned_data.get('delete'):
                    return self._folder_form_delete(
                        request,
                        original,
                    )

                folder = form.save()
                if original:
                    self.message_user(
                        request,
                        _('The folder "%s" was changed successfully.') % folder,  # noqa
                        messages.SUCCESS)
                    return HttpResponseRedirect(
                        reverse('admin:%s_%s_changelist' % info) +
                        (('?folder__id__exact=%s' % folder.parent_id)
                         if folder.parent_id else '')
                    )

                else:
                    self.message_user(
                        request,
                        _('The folder "%s" was added successfully.') % folder,
                        messages.SUCCESS)
                    return HttpResponseRedirect(
                        reverse('admin:%s_%s_changelist' % info) +
                        '?folder__id__exact=%s' % folder.pk
                    )

        else:
            form = FolderForm(**kw)

        adminForm = helpers.AdminForm(
            form,
            [[None, {'fields': list(form.fields.keys())}]],
            {},
            (),
            model_admin=self)

        response = self.render_change_form(
            request,
            dict(
                self.admin_site.each_context(request),
                title=(
                    _('Add %s') if add else _('Change %s')
                ) % Folder._meta.verbose_name,
                adminform=adminForm,
                object_id=original.pk if original else None,
                original=original,
                is_popup=False,
                media=self.media + adminForm.media,
                errors=helpers.AdminErrorList(form, []),
                preserve_filters=self.get_preserved_filters(request),
            ),
            add=add,
            change=not add,
            form_url='.',
            obj=original,
        )
        response.template_name = [
            'admin/cabinet/folder/change_form.html',
            'admin/change_form.html',
        ]
        return response

    def _folder_form_delete(self, request, obj):
        if not self.has_delete_permission(request, obj):
            raise PermissionDenied

        using = router.db_for_write(obj.__class__)

        # Populate deleted_objects, a data structure of all related objects
        # that will also be deleted.
        (deleted_objects, model_count, perms_needed, protected) = get_deleted_objects(  # noqa
            [obj], obj._meta, request.user, self.admin_site, using)

        if protected or perms_needed:
            self.message_user(
                request,
                _('Cannot delete %(name)s') % {'name': obj._meta.verbose_name},
                messages.ERROR,
            )

        elif len(deleted_objects) > 1:
            self.message_user(
                request,
                _('Cannot delete %(name)s because of related objects (%(related)s)') % {  # noqa
                    'name': obj._meta.verbose_name,
                    'related': ', '.join(
                        '%s %s' % (count, name)
                        for name, count in model_count.items()
                    ),
                },
                messages.ERROR,
            )

        else:
            obj.delete()
            self.message_user(
                request,
                _('The folder "%s" was deleted successfully.') % obj,
                messages.SUCCESS)

        info = self.model._meta.app_label, self.model._meta.model_name
        return HttpResponseRedirect(
            reverse('admin:%s_%s_changelist' % info) +
            (('?folder__id__exact=%s' % obj.parent_id)
             if obj.parent_id else '')
        )

    def admin_thumbnail(self, instance):
        if instance.image_file.name:
            return format_html(
                '<img src="{}" alt=""/>',
                instance.image_file.crop['50x50'],
            )
        elif instance.download_file.name:
            return instance.download_type.upper()
        return ''
    admin_thumbnail.short_description = ''

    def admin_file_name(self, instance):
        return instance.file_name
    admin_file_name.short_description = _('file name')

    def admin_details(self, instance):
        return format_html(
            '<small>{}<br>{}</small>',
            filesizeformat(instance.file_size),
            instance.file.name,
        )
    admin_details.short_description = _('details')
