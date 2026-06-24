alter table public.users
drop constraint if exists users_role_check;

alter table public.users
add constraint users_role_check
check (role in ('Member', 'Leader', 'Partner', 'Admin'));

create or replace function public.getexpert_can_view_member(target_email text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select
    target_email = lower(auth.email())
    or public.getexpert_is_admin()
    or exists (
      select 1
      from public.users owner
      join public.member_profiles owner_profile on owner_profile.email = owner.email
      join public.member_profiles target_profile on target_profile.email = target_email
      where owner.user_id = auth.uid()
        and owner.role in ('Leader', 'Partner')
        and owner_profile.team_id = target_profile.team_id
    );
$$;

drop policy if exists users_admin_update on public.users;
create policy users_admin_update on public.users
for update to authenticated
using (public.getexpert_is_admin())
with check (role in ('Member', 'Leader', 'Partner', 'Admin'));

drop policy if exists teams_read on public.teams;
create policy teams_read on public.teams
for select to authenticated
using (
  public.getexpert_is_admin()
  or exists (
    select 1
    from public.member_profiles profile
    where profile.email = lower(auth.email())
      and profile.team_id = teams.team_id
  )
);

create or replace function public.getexpert_resolve_team_invite(
  requested_invite_code text
)
returns table(team_id text, team_data jsonb)
language sql
stable
security definer
set search_path = public
as $$
  select team.team_id, team.team_data
  from public.teams team
  where lower(team.team_data->>'invite_code') = lower(trim(requested_invite_code))
  limit 1;
$$;

revoke all on function public.getexpert_resolve_team_invite(text) from public;
grant execute on function public.getexpert_resolve_team_invite(text) to authenticated;

drop function if exists public.getexpert_set_team_invite(text, text);

create or replace function public.getexpert_set_team_invite(
  target_team_id text,
  new_invite_code text,
  invite_owner_role text,
  invite_referral_rate numeric,
  invite_owner_user_id text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  caller_email text := lower(auth.email());
  caller_role text;
  current_owner_email text;
  expected_rate numeric;
begin
  select role
  into caller_role
  from public.users
  where user_id = auth.uid();

  if caller_role not in ('Leader', 'Partner', 'Admin') then
    raise exception 'permission denied';
  end if;

  select lower(coalesce(team_data->>'leader_email', ''))
  into current_owner_email
  from public.teams
  where team_id = target_team_id;

  if not found then
    raise exception 'team not found';
  end if;

  if caller_role <> 'Admin' and current_owner_email <> caller_email then
    raise exception 'permission denied';
  end if;

  expected_rate := case invite_owner_role
    when 'Partner' then 15
    when 'Leader' then 8
    else 0
  end;

  if caller_role <> 'Admin'
     and (invite_owner_role <> caller_role or invite_referral_rate <> expected_rate) then
    raise exception 'invalid referral metadata';
  end if;

  if caller_role <> 'Admin'
     and invite_owner_user_id <> auth.uid()::text then
    raise exception 'invalid referrer';
  end if;

  update public.teams
  set team_data = jsonb_set(
        jsonb_set(
          jsonb_set(
            jsonb_set(team_data, '{invite_code}', to_jsonb(trim(new_invite_code)), true),
            '{invite_owner_role}', to_jsonb(invite_owner_role), true
          ),
          '{invite_referral_rate}', to_jsonb(invite_referral_rate), true
        ),
        '{invite_owner_user_id}', to_jsonb(invite_owner_user_id), true
      ),
      updated_by = caller_email,
      updated_at = now()
  where team_id = target_team_id;
end;
$$;

revoke all on function public.getexpert_set_team_invite(
  text, text, text, numeric, text
) from public;
grant execute on function public.getexpert_set_team_invite(
  text, text, text, numeric, text
) to authenticated;

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
  team_owner_email text;
begin
  select role
  into caller_role
  from public.users
  where user_id = auth.uid();

  if caller_role not in ('Leader', 'Partner', 'Admin') then
    raise exception 'permission denied';
  end if;

  select lower(coalesce(team_data->>'leader_email', ''))
  into team_owner_email
  from public.teams
  where team_id = target_team_id;

  if not found then
    raise exception 'team not found';
  end if;

  if caller_role <> 'Admin' and team_owner_email <> caller_email then
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
