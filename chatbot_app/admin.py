from django.contrib import admin
from .models import ChatMessage, UserAttribute, UserActivity, UserProfile, ActivityAnalytics, UserRelationship

# Register your models here.

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'affinity_score')
    search_fields = ('user__username',)

class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'is_user', 'timestamp')
    list_filter = ('is_user', 'user')
    search_fields = ('user__username', 'message')
    list_per_page = 20

class UserAttributeAdmin(admin.ModelAdmin):
    list_display = ('user', 'fact_type', 'content', 'created_at')
    list_filter = ('fact_type', 'user')
    search_fields = ('user__username', 'fact_type', 'content')
    list_per_page = 20

class UserActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'activity_date', 'place', 'companion', 'memo', 'created_at')
    list_filter = ('activity_date', 'user')
    search_fields = ('user__username', 'place', 'companion', 'memo')
    list_per_page = 20

class ActivityAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('user', 'period_type', 'period_start_date', 'place', 'companion', 'count')
    list_filter = ('period_type', 'period_start_date', 'place', 'companion')
    search_fields = ('user__username', 'place', 'companion')
    list_per_page = 20

class UserRelationshipAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'relationship_type', 'position', 'disambiguator', 'traits', 'created_at')
    list_filter = ('relationship_type', 'position', 'user')
    search_fields = ('user__username', 'name', 'relationship_type', 'traits', 'disambiguator')
    list_per_page = 20

admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(ChatMessage, ChatMessageAdmin)
admin.site.register(UserAttribute, UserAttributeAdmin)
admin.site.register(UserActivity, UserActivityAdmin)
admin.site.register(ActivityAnalytics, ActivityAnalyticsAdmin)
admin.site.register(UserRelationship, UserRelationshipAdmin)
