from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

class TestRolesView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        roles = list(user.roles.values_list('role', flat=True))
        
        return Response({
            'email': user.email,
            'roles': roles,
            'has_admin': 'admin' in roles,
            'message': 'If you see has_admin: true, the backend is working correctly'
        })
