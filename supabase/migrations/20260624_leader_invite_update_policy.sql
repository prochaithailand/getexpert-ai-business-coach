drop policy if exists teams_leader_invite_update on public.teams;
create policy teams_leader_invite_update on public.teams
for update to authenticated
using (
  exists (
    select 1
    from public.users
    where user_id = auth.uid()
      and role = 'Leader'
      and lower(email) = lower(teams.team_data->>'leader_email')
  )
)
with check (
  exists (
    select 1
    from public.users
    where user_id = auth.uid()
      and role = 'Leader'
      and lower(email) = lower(teams.team_data->>'leader_email')
  )
);
