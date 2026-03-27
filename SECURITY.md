# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| Latest  | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it privately:

1. **Do NOT create a public issue**
2. Use [GitHub Security Advisories](https://github.com/myshdd/server-monitor/security/advisories/new)
3. Or email: (add your email if you want)

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response Time

- Initial response: within 48 hours
- Fix timeline: depends on severity
- Public disclosure: after fix is released

## Security Best Practices

### When Using This Project

- **Never commit secrets** (tokens, passwords, API keys)
- Store sensitive data in `config/secrets.json` (chmod 600)
- Keep `secrets.json` in `.gitignore`
- Regularly update dependencies
- Use strong, unique passwords
- Enable 2FA for your Telegram account
- Restrict `ALLOWED_USER_ID` to trusted users only

### Fail2ban

- Review banned IPs regularly
- Adjust thresholds based on your traffic
- Monitor for false positives

### GeoIP Blocking

- Keep whitelist IPs updated
- Test DDNS resolution regularly
- Update GeoIP databases monthly

### Docker

- Use official images when possible
- Keep containers updated
- Review container logs for anomalies

### SSH Security

- Use SSH keys instead of passwords
- Disable root login
- Use non-standard SSH port (optional)
- Monitor `/var/log/auth.log`

## Known Issues

Check [Issues](https://github.com/myshdd/server-monitor/issues) for known security-related bugs.

---

Thank you for helping keep Server Monitor secure! 🔒
