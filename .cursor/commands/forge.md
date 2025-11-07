git add -A \
&& git commit -m "{{input:Commit message}}" \
&& git push origin "$(git rev-parse --abbrev-ref HEAD)" \
&& sleep 20 \
&& ssh pi-forge 'cd /home/admin/js-craw && ./scripts/deployment/verify-deployment.sh'

