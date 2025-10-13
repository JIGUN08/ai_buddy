import uuid
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# Create your models here.

class UserProfile(models.Model):
    """
    사용자 프로필을 저장하는 모델
    - user: Django의 기본 User 모델과 1:1 관계
    - affinity_score: AI '아이'와의 호감도 점수
    - memory: 사용자에 대한 정보를 JSON 형태로 저장 (예: {"facts": ["사용자는 고양이를 좋아한다"], "name": "홍길동"})
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    affinity_score = models.IntegerField(default=0, help_text="AI '아이'와의 호감도 점수")
    memory = models.JSONField(default=dict, help_text="사용자에 대한 기억 저장소")

    def __str__(self):
        return f"{self.user.username}의 프로필"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """User가 생성될 때 자동으로 UserProfile을 생성합니다."""
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """User가 저장될 때 UserProfile도 함께 저장합니다."""
    try:
        instance.profile.save()
    except UserProfile.DoesNotExist:
        # admin 등에서 profile이 없는 user를 다룰 때를 대비
        UserProfile.objects.create(user=instance)

class ChatMessage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    is_user = models.BooleanField(default=True)  # True면 사용자 메시지, False면 AI 메시지
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.username}: {self.message[:50]}'

class UserAttribute(models.Model):
    """
    사용자의 불변의 속성(성격, MBTI, 생일, 신체 특징 등)를 저장하는 모델
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attributes')
    fact_type = models.CharField(max_length=100, help_text="속성의 종류 (예: '성격', 'MBTI', '생일')", null=True, blank=True)
    content = models.CharField(max_length=255, help_text="속성 내용 (예: '털털함', 'INFP', '1995-10-31')", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'fact_type', 'content') # 중복 정보 방지

    def __str__(self):
        return f"{self.user.username}의 속성 - {self.fact_type}: {self.content}"

class UserActivity(models.Model):
    """
    사용자의 활동 기록(일기장)을 저장하는 모델
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    activity_date = models.DateField(help_text="활동 날짜", null=True, blank=True)
    activity_time = models.TimeField(null=True, blank=True, help_text="활동 시간")
    place = models.CharField(max_length=255, null=True, blank=True, help_text="장소")
    companion = models.CharField(max_length=255, null=True, blank=True, help_text="동행인")
    memo = models.TextField(null=True, blank=True, help_text="활동 관련 메모 또는 대화 내용")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.activity_date}] {self.user.username}'s activity at {self.place}"

class ActivityAnalytics(models.Model):
    """
    사용자의 활동을 주/월/년 단위로 요약하여 통계를 저장하는 모델
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='analytics')
    period_type = models.CharField(max_length=10, choices=[('weekly', '주간'), ('monthly', '월간'), ('yearly', '연간')])
    period_start_date = models.DateField(help_text="통계 기간의 시작일")
    place = models.CharField(max_length=255, db_index=True, help_text="장소")
    companion = models.CharField(max_length=255, null=True, blank=True, db_index=True, help_text="동행인")
    count = models.PositiveIntegerField(default=0, help_text="해당 기간 동안의 방문 횟수")

    class Meta:
        unique_together = ('user', 'period_type', 'period_start_date', 'place', 'companion')

    def __str__(self):
        return f"[{self.period_start_date} {self.period_type}] {self.user.username} at {self.place}: {self.count}"

class UserRelationship(models.Model):
    """
    사용자의 인간관계 정보를 저장하는 모델
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='relationships')
    serial_code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, help_text="동일 인물 구분을 위한 고유 시리얼 코드") # New field
    relationship_type = models.CharField(max_length=100, help_text="관계 유형 (예: 가족, 친구, 직장 동료)")
    position = models.CharField(max_length=100, null=True, blank=True, help_text="관계 내 포지션 (예: 오빠, 친한 친구, 상사)")
    name = models.CharField(max_length=100, help_text="상대방 이름")
    disambiguator = models.CharField(max_length=100, null=True, blank=True, help_text="동명이인 구분을 위한 식별자 (예: '개발팀', '친구')")
    traits = models.TextField(null=True, blank=True, help_text="상대방 성격 또는 특징")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Update unique_together to use serial_code instead of name and disambiguator
        unique_together = ('user', 'serial_code') 

    def __str__(self):
        return f"{self.user.username} - {self.name} ({self.relationship_type}) [{self.serial_code}]"
