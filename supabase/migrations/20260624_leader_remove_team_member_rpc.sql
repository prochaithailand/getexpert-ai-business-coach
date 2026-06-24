create or replace function public.getexpert_remove_team_member(
  target_team_id text,
  target_member_email text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  caller_email text := lower(auth.email());
  caller_role text;
  team_leader_email text;
begin
  select role
  into caller_role
  from public.users
  where user_id = auth.uid();

  if caller_role not in ('Leader', 'Admin') then
    raise exception 'permission denied';
  end if;

  select lower(coalesce(team_data->>'leader_email', ''))
  into team_leader_email
  from public.teams
  where team_id = target_team_id;

  if not found then
    raise exception 'team not found';
  end if;

  if caller_role = 'Leader' and team_leader_email <> caller_email then
    raise exception 'permission denied';
  end if;

  if not exists (
    select 1
    from public.member_profiles profile
    join public.users account on account.email = profile.email
    where lower(profile.email) = lower(target_member_email)
      and profile.team_id = target_team_id
      and account.role = 'Member'
  ) then
    raise exception 'member not found in team';
  end if;

  update public.member_profiles
  set team_id = null,
      profile_data = jsonb_set(
        jsonb_set(
          jsonb_set(
            jsonb_set(
              jsonb_set(profile_data, '{team_id}', '""'::jsonb, true),
              '{team_name}', '""'::jsonb, true
            ),
            '{team_leader}', '""'::jsonb, true
          ),
          '{invited_by}', '""'::jsonb, true
        ),
        '{joined_at}', '""'::jsonb, true
      ),
      updated_at = now()
  where lower(email) = lower(target_member_email)
    and team_id = target_team_id;
end;
$$;

revoke all on function public.getexpert_remove_team_member(text, text) from public;
grant execute on function public.getexpert_remove_team_member(text, text) to authenticated;
