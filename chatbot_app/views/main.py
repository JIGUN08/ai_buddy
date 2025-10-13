from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from ..models import UserProfile, ChatMessage, UserAttribute, UserRelationship

@login_required
def index(request):
    """메인 채팅 페이지를 렌더링합니다.

    로그인한 사용자의 프로필 정보와 이전 채팅 기록을 가져와
    템플릿에 전달합니다.
    """
    user_profile = UserProfile.objects.get(user=request.user)
    chat_messages_data = list(ChatMessage.objects.filter(user=request.user).order_by('timestamp').values('message', 'is_user', 'timestamp'))
    return render(request, 'index.html', {'user_profile': user_profile, 'chat_messages': chat_messages_data})

@login_required
def ai_status(request):
    """AI의 상태(기억, 호감도 등)를 보여주는 페이지를 렌더링합니다."""
    user_profile = UserProfile.objects.get(user=request.user)
    affinity_score = user_profile.affinity_score
    core_facts = list(
        UserAttribute.objects.filter(user=request.user).values('fact_type', 'content')
    )
    # Serialize relationships for pagination in JavaScript
    user_relationships = list(
        UserRelationship.objects.filter(user=request.user).order_by('name').values(
            'serial_code', 'name', 'relationship_type', 'position', 'traits'
        )
    )
    return render(request, 'ai_status.html', {
        'user_profile': user_profile,
        'affinity_score': affinity_score,
        'core_facts': core_facts,
        'user_relationships': user_relationships
    })
