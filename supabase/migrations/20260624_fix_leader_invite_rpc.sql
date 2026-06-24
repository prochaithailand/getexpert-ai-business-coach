drop policy if exists teams_leader_invite_update on public.teams;

create or replace function public.getexpert_set_team_invite(
  target_team_id text,
  new_invite_code text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  caller_email text := lower(auth.email());
  caller_role text;
  current_leader_email text;
begin
  select role
  into caller_role
  from public.users
  where user_id = auth.uid();

  if caller_role not in ('Leader', 'Admin') then
    raise exception 'permission denied';
  end if;

  select lower(coalesce(team_data->>'leader_email', ''))
  into current_leader_email
  from public.teams
  where team_id = target_team_id;

  if not found then
    raise exception 'team not found';
  end if;

  if caller_role = 'Leader' and current_leader_email <> caller_email then
    raise exception 'permission denied';
  end if;

  update public.teams
  set team_data = jsonb_set(
        team_data,
        '{invite_code}',
        to_jsonb(trim(new_invite_code)),
        true
      ),
      updated_by = caller_email,
      updated_at = now()
  where team_id = target_team_id;
end;
$$;

revoke all on function public.getexpert_set_team_invite(text, text) from public;
grant execute on function public.getexpert_set_team_invite(text, text) to authenticated;
