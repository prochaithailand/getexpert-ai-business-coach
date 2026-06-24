drop policy if exists profiles_admin_insert on public.member_profiles;
create policy profiles_admin_insert on public.member_profiles
for insert to authenticated
with check (public.getexpert_is_admin());

with leader_matches as (
  select distinct on (team.team_id)
    team.team_id,
    lower(account.email) as email
  from public.teams as team
  join public.users as account
    on account.role = 'Leader'
  left join public.member_profiles as profile
    on profile.email = account.email
  where profile.team_id = team.team_id
     or lower(account.full_name) = lower(team.team_data->>'leader')
  order by team.team_id, (profile.team_id = team.team_id) desc
)
update public.teams as team
set team_data = jsonb_set(
  team.team_data,
  '{leader_email}',
  to_jsonb(matched.email),
  true
)
from leader_matches as matched
where matched.team_id = team.team_id
  and coalesce(team.team_data->>'leader_email', '') = '';
