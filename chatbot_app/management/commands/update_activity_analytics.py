from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone # [수정] timezone 모듈 사용
from datetime import timedelta, datetime
from chatbot_app.models import UserActivity, ActivityAnalytics, User

class Command(BaseCommand):
    help = 'UserActivity(사용자 활동) 항목을 기반으로 ActivityAnalytics(활동 분석) 테이블을 업데이트합니다.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('활동 분석 업데이트를 시작합니다...'))

        # 활동 기록이 있는 사용자만 가져와 처리합니다. (효율성 개선)
        users = User.objects.filter(useractivity__isnull=False).distinct()

        for user in users:
            self.stdout.write(f'--- {user.username} 사용자의 활동을 처리합니다. ---')
            
            # 해당 사용자의 모든 활동 기록을 가져옵니다.
            user_activities = UserActivity.objects.filter(user=user).order_by('activity_date')

            grouped_activities = {}
            for mem in user_activities:
                key = (mem.place, mem.companion if mem.companion else '')
                if key not in grouped_activities:
                    grouped_activities[key] = []
                grouped_activities[key].append(mem)

            for (place, companion_str), activities in grouped_activities.items():
                companion = companion_str if companion_str else None

                # 각 기간 유형(주/월/년)별로 통계를 집계하는 함수를 호출합니다.
                self._aggregate_for_period(user, place, companion, activities, 'weekly')
                self._aggregate_for_period(user, place, companion, activities, 'monthly')
                self._aggregate_for_period(user, place, companion, activities, 'yearly')
        
        self.stdout.write(self.style.SUCCESS('활동 분석 업데이트가 완료되었습니다.'))

    def _aggregate_for_period(self, user, place, companion, activities, period_type):
        """주어진 기간 유형(주/월/년)에 따라 활동을 집계하는 헬퍼 함수입니다."""
        period_counts = {}

        for activity in activities:
            # activity_date는 날짜(date) 객체이므로 _get_period_start_date로 전달합니다.
            start_date = self._get_period_start_date(activity.activity_date, period_type)
            if start_date not in period_counts:
                period_counts[start_date] = 0
            period_counts[start_date] += 1
        
        # 집계된 횟수 정보를 ActivityAnalytics 테이블에 저장하거나 업데이트합니다.
        for start_date, count in period_counts.items():
            ActivityAnalytics.objects.update_or_create(
                user=user,
                period_type=period_type,
                period_start_date=start_date, # start_date는 이미 date 객체
                place=place,
                companion=companion,
                defaults={'count': count}
            )
            self.stdout.write(f'  - {user.username}의 {period_type} 활동 업데이트: {place} ({start_date}) => {count}회')


    def _get_period_start_date(self, date_obj, period_type):
        """특정 날짜가 속한 기간의 시작 날짜를 반환하는 헬퍼 함수입니다."""
        
        # date_obj를 로컬 시간대 정보가 없는 date 객체로 가정하고 처리합니다.
        # timezone.localdate()는 현재 로컬 시간대의 '오늘 날짜'를 반환하므로,
        # 이 함수에서는 순수 날짜 계산만 수행합니다.

        if period_type == 'weekly':
            # 해당 날짜가 속한 주의 월요일 날짜를 반환합니다. (월요일: 0, 일요일: 6)
            return date_obj - timedelta(days=date_obj.weekday())
        elif period_type == 'monthly':
            # 해당 날짜가 속한 달의 1일을 반환합니다.
            return date_obj.replace(day=1)
        elif period_type == 'yearly':
            # 해당 날짜가 속한 해의 1월 1일을 반환합니다.
            return date_obj.replace(month=1, day=1)
        return date_obj
