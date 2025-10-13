from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta, datetime
from chatbot_app.models import UserActivity, ActivityAnalytics, User

class Command(BaseCommand):
    # 'python manage.py help update_activity_analytics' 실행 시 표시되는 도움말입니다.
    help = 'UserActivity(사용자 활동) 항목을 기반으로 ActivityAnalytics(활동 분석) 테이블을 업데이트합니다.'

    def handle(self, *args, **options):
        # 스크립트 시작을 알리는 로그를 콘솔에 출력합니다.
        self.stdout.write(self.style.SUCCESS('활동 분석 업데이트를 시작합니다...'))

        # 데이터베이스에 있는 모든 사용자를 가져옵니다.
        users = User.objects.all()

        # 각 사용자에 대해 개별적으로 분석을 수행합니다.
        for user in users:
            self.stdout.write(f'{user.username} 사용자의 활동을 처리합니다.')
            
            # 해당 사용자의 모든 활동 기록(UserActivity)을 날짜순으로 가져옵니다.
            # [설명] 실제 운영 환경에서는 새로 추가되었거나 아직 처리되지 않은 기록만,
            # 또는 마지막 분석 이후의 기록만 처리하는 것이 더 효율적일 수 있습니다.
            # 여기서는 단순화를 위해 모든 기록을 처리하도록 구현했습니다.
            user_activities = UserActivity.objects.filter(user=user).order_by('activity_date')

            # 통계를 집계하기 위해 활동들을 (장소, 동행인) 기준으로 그룹화할 딕셔너리입니다.
            grouped_activities = {}
            for mem in user_activities:
                # 그룹화를 위해 (장소, 동행인) 튜플을 딕셔너리의 키(key)로 사용합니다.
                # 동행인이 없는 경우 빈 문자열로 처리합니다.
                key = (mem.place, mem.companion if mem.companion else '')
                if key not in grouped_activities:
                    grouped_activities[key] = []
                grouped_activities[key].append(mem)

            # 그룹화된 활동들을 하나씩 처리합니다.
            for (place, companion_str), activities in grouped_activities.items():
                # 그룹화 과정에서 사용된 빈 문자열('')을 다시 None으로 변환합니다. (DB 저장을 위해)
                companion = companion_str if companion_str else None

                # 각 기간 유형(주/월/년)별로 통계를 집계하는 함수를 호출합니다.
                self._aggregate_for_period(user, place, companion, activities, 'weekly')
                self._aggregate_for_period(user, place, companion, activities, 'monthly')
                self._aggregate_for_period(user, place, companion, activities, 'yearly')
        
        # 모든 작업이 완료되었음을 알리는 로그를 콘솔에 출력합니다.
        self.stdout.write(self.style.SUCCESS('활동 분석 업데이트가 완료되었습니다.'))

    def _aggregate_for_period(self, user, place, companion, activities, period_type):
        # 주어진 기간 유형(주/월/년)에 따라 활동을 집계하는 헬퍼(도우미) 함수입니다.
        # key: 기간 시작일, value: 활동 횟수
        period_counts = {}

        # 해당 그룹의 모든 활동을 순회합니다.
        for activity in activities:
            # 활동 날짜(activity.activity_date)를 기준으로 해당 기간(주/월/년)의 시작 날짜를 가져옵니다.
            start_date = self._get_period_start_date(activity.activity_date, period_type)
            if start_date not in period_counts:
                period_counts[start_date] = 0
            period_counts[start_date] += 1
        
        # 집계된 횟수 정보를 ActivityAnalytics 테이블에 저장하거나 업데이트합니다.
        for start_date, count in period_counts.items():
            # update_or_create: 주어진 조건(user, period_type 등)에 맞는 데이터가 있으면 defaults 값으로 업데이트하고, 없으면 새로 생성합니다.
            # 이를 통해 동일한 기간/장소/동행인에 대한 통계가 중복으로 쌓이는 것을 방지합니다.
            ActivityAnalytics.objects.update_or_create(
                user=user,
                period_type=period_type,
                period_start_date=start_date,
                place=place,
                companion=companion,
                defaults={'count': count}
            )
            self.stdout.write(f'  - {user.username}의 {period_type} 활동 업데이트: {place} ({start_date}) => {count}회')


    def _get_period_start_date(self, date_obj, period_type):
        # 특정 날짜가 속한 기간의 시작 날짜를 반환하는 헬퍼(도우미) 함수입니다.
        if period_type == 'weekly':
            # 해당 날짜가 속한 주의 월요일 날짜를 반환합니다.
            return date_obj - timedelta(days=date_obj.weekday())
        elif period_type == 'monthly':
            # 해당 날짜가 속한 달의 1일을 반환합니다.
            return date_obj.replace(day=1)
        elif period_type == 'yearly':
            # 해당 날짜가 속한 해의 1월 1일을 반환합니다.
            return date_obj.replace(month=1, day=1)
        return date_obj # 정상적인 경우 이 코드는 실행되지 않습니다.
