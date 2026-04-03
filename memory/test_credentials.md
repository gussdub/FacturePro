# Test Credentials

## Exempt User (always active, bypasses subscription)
- Email: gussdub@gmail.com
- Password: testpass123
- Subscription Status: active (exempt)

## Notes
- New registered users get 14-day free trial (subscription_status: "trial")
- After trial expires, status becomes "expired" and user is redirected to /subscription page
- Exempt users are defined in EXEMPT_USERS list in server.py
