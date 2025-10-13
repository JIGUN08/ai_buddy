# chatbot_app/management/commands/update_activity_analytics.py (효율성을 위한 재구성)

from django.core.management.base import BaseCommand
from django.db.models import Count, Min, Max
from django.db.models.functions import TruncWeek, TruncMonth, TruncYear
from django.utils import timezone
from datetime import timedelta, datetime
from chatbot_app.models import UserActivity, ActivityAnalytics, User

class Command(BaseCommand):
    help = 'UserActivity 항목을 기반으로 ActivityAnalytics 테이블을 업데이트합니다. (DB 집계 방식)'
    
    # 분석할 기간 타입 정의
    PERIOD_TYPES = {
        'weekly': TruncWeek,
        'monthly': TruncMonth,
        'yearly': TruncYear
    }

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('활동 분석 업데이트를 시작합니다...'))
        
        # 오늘 날짜를 기준으로 과거 12개월 이내의 활동만 처리하는 것이 일반적입니다.
        # 여기서는 단순화를 위해 전체 데이터를 처리합니다.
        
        # 각 기간 유형별로 집계를 수행합니다.
        for period_type, trunc_func in self.PERIOD_TYPES.items():
            self.stdout.write(f'-- {period_type} 분석을 시작합니다.')
            
            # 1. DB에서 직접 그룹화 및 집계 수행
            # companion 필드의 NULL/None 값 처리에 주의 (SQLite와 PostgreSQL의 차이가 있을 수 있음)
            analytics_data = UserActivity.objects.values(
                'user_id',
                'place',
                'companion',
                period_start_date=trunc_func('activity_date') # 기간 시작 날짜 계산
            ).annotate(
                count=Count('id') # 그룹별 횟수 계산
            ).order_by() # 불필요한 정렬 제거
            
            # 2. 집계 결과를 ActivityAnalytics 테이블에 저장/업데이트
            for data in analytics_data:
                # companion이 None인 경우 처리 (values() 결과는 None 또는 문자열)
                companion_val = data['companion'] if data['companion'] else None
                
                # update_or_create를 사용하여 효율적으로 저장/업데이트
                ActivityAnalytics.objects.update_or_create(
                    user_id=data['user_id'],
                    period_type=period_type,
                    period_start_date=data['period_start_date'],
                    place=data['place'],
                    companion=companion_val,
                    defaults={'count': data['count']}
                )
                
                # 로그 출력 (선택 사항)
                self.stdout.write(
                    f'  - {data["user_id"]} ({period_type}): {data["place"]} ({data["period_start_date"].date()}) => {data["count"]}회'
                )

        self.stdout.write(self.style.SUCCESS('활동 분석 업데이트가 완료되었습니다.'))
