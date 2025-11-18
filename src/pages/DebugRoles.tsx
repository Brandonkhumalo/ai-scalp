import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";
import { useUserRole } from "@/hooks/useUserRole";

export default function DebugRoles() {
  const [loginData, setLoginData] = useState<any>(null);
  const [meData, setMeData] = useState<any>(null);
  const [cachedUser, setCachedUser] = useState<any>(null);
  const { data: hookRoles, isLoading } = useUserRole();

  useEffect(() => {
    // Check localStorage
    const user = localStorage.getItem('user');
    if (user) {
      setCachedUser(JSON.parse(user));
    }

    // Call /me endpoint
    apiClient.getMe().then(data => {
      setMeData(data);
    }).catch(err => {
      setMeData({ error: err.message });
    });
  }, []);

  return (
    <div style={{ padding: '20px', fontFamily: 'monospace', fontSize: '14px' }}>
      <h1>Role Debugging Info</h1>
      
      <h2>1. localStorage user data:</h2>
      <pre>{JSON.stringify(cachedUser, null, 2)}</pre>
      
      <h2>2. /me API response:</h2>
      <pre>{JSON.stringify(meData, null, 2)}</pre>
      
      <h2>3. useUserRole hook data:</h2>
      <pre>Loading: {isLoading ? 'true' : 'false'}</pre>
      <pre>Roles: {JSON.stringify(hookRoles, null, 2)}</pre>
      
      <h2>4. Test:</h2>
      <p>Has admin role: {hookRoles && hookRoles.includes('admin') ? 'YES ✅' : 'NO ❌'}</p>
      {hookRoles && hookRoles.includes('admin') && (
        <a href="/admin" style={{ color: 'blue', textDecoration: 'underline' }}>
          Admin Link (should show if admin)
        </a>
      )}
    </div>
  );
}
