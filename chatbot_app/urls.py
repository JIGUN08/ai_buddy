from django.urls import path
from .views import main, chatWithAi, auth

urlpatterns = [
    path('', main.index, name='index'),
    path('chat/', chatWithAi.chat_response, name='chat_response'),
    path('signup/', auth.signup_view, name='signup'),
    path('login/', auth.login_view, name='login'),
    path('logout/', auth.logout_view, name='logout'),
    path('ai_status/', main.ai_status, name='ai_status'),
]
