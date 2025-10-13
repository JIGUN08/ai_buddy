from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q
from konlpy.tag import Okt
from ..models import UserActivity

def get_activity_recommendation(user, user_message):
    """
    사용자 메시지를 기반으로 활동 추천을 생성합니다.
    """
    # '추천', '갈만한' 등의 키워드가 있을 때만 작동
    if '추천' not in user_message and '갈만한' not in user_message:
        return ""

    # '카페' 추천 로직
    if '카페' in user_message:
        seven_days_ago = timezone.now().date() - timedelta(days=7)
        recent_cafe_visits = UserActivity.objects.filter(
            user=user,
            place__icontains='카페',
            activity_date__gte=seven_days_ago
        ).values('place').annotate(visit_count=Count('place')).order_by('-visit_count')

        if not recent_cafe_visits:
            return ""

        most_visited = recent_cafe_visits[0]
        if most_visited['visit_count'] > 1:
            recommendation = f"이번 주에 {most_visited['place']}은(는) {most_visited['visit_count']}번이나 갔네. 오늘은 다른 곳에 가보는 건 어때? 예를 들면 새로운 동네 카페라던가."
            return f"[시스템 정보: 사용자의 활동 기록을 바탕으로 다음 추천을 생성했어. 이 내용을 참고해서 자연스럽게 제안해봐: '{recommendation}']"
            
    return ""

def search_activities_for_context(user, user_message):
    """
    사용자 메시지의 키워드를 바탕으로 UserActivity를 검색하여 컨텍스트를 생성합니다.
    """
    try:
        okt = Okt()
        # 사용자 메시지에서 명사만 추출하여 검색 키워드로 사용
        keywords = [word for word, pos in okt.pos(user_message, stem=True) if pos == 'Noun']
        
        if not keywords:
            return ""

        # Q 객체를 사용하여 여러 필드에서 OR 조건으로 검색
        query = Q()
        for keyword in keywords:
            query |= Q(memo__icontains=keyword)
            query |= Q(place__icontains=keyword)
            query |= Q(companion__icontains=keyword)

        # 현재 사용자의 기억만 대상으로 검색, 최근 순으로 3개까지
        search_results = UserActivity.objects.filter(user=user).filter(query).order_by('-activity_date')[:10]

        if not search_results:
            return ""

        # 검색 결과를 컨텍스트 문자열로 포맷
        result_strings = []
        for mem in search_results:
            base_string = ""
            if mem.activity_date:
                base_string = f"'{mem.activity_date.strftime('%Y-%m-%d')}'의 기억(장소: {mem.place or 'N/A'}, "
            else:
                base_string = f"'날짜 미상'의 기억(장소: {mem.place or 'N/A'}, "
            
            base_string += f"동행: {mem.companion or 'N/A'}, 메모: {mem.memo or 'N/A'})"
            result_strings.append(base_string)
        
        search_context = "[관련 기억 검색 결과: " + ", ".join(result_strings) + "]"
        return search_context

    except Exception as e:
        print(f"--- Could not perform activity search due to an error: {e} ---")
        return ""
