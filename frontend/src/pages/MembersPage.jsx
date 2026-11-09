import { useCallback, useEffect, useRef, useState } from 'react';
import { Plus, Search, UserPlus, Users } from 'lucide-react';

import { getErrorMessage, membersApi } from '../api/client';
import { useToast } from '../context/ToastContext';
import { PAGE_SIZE } from '../utils/constants';
import { PageHeader } from '../components/PageHeader';
import { ErrorBanner } from '../components/ErrorBanner';
import { EmptyState } from '../components/EmptyState';
import { Skeleton } from '../components/Loader';
import { Pagination } from '../components/Pagination';
import { MemberCard } from '../components/MemberCard';
import { MemberForm } from '../components/MemberForm';
import { ConfirmDialog } from '../components/ConfirmDialog';

const ROLE_TABS = [
  { value: '', label: 'All people' },
  { value: 'MEMBER', label: 'Members' },
  { value: 'VISITOR', label: 'Visitors' },
];

export function MembersPage() {
  const toast = useToast();
  const [members, setMembers] = useState([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [roleFilter, setRoleFilter] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);
  const [formOpen, setFormOpen] = useState(false);
  const [editingMember, setEditingMember] = useState(null);
  const [confirmMember, setConfirmMember] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [enrollingId, setEnrollingId] = useState(null);
  const requestIdRef = useRef(0);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(1);
      setSearch(searchInput.trim());
    }, 350);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const loadMembers = useCallback(async () => {
    // Ignore responses from superseded searches/filters (out-of-order replies).
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    setLoading(true);
    setError('');
    try {
      const params = { page, page_size: PAGE_SIZE };
      if (search) params.search = search;
      if (roleFilter) params.role = roleFilter;
      const { data } = await membersApi.list(params);
      if (requestId !== requestIdRef.current) return;
      setMembers(data.results);
      setCount(data.count);
    } catch (loadError) {
      if (requestId !== requestIdRef.current) return;
      setError(getErrorMessage(loadError, 'Could not load members.'));
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  }, [page, search, roleFilter]);

  useEffect(() => {
    loadMembers();
  }, [loadMembers, refreshKey]);

  const openCreate = () => {
    setEditingMember(null);
    setFormOpen(true);
  };

  const openEdit = (member) => {
    setEditingMember(member);
    setFormOpen(true);
  };

  const handleSaved = (_member, { created } = {}) => {
    if (created) setPage(1);
    setRefreshKey((current) => current + 1);
  };

  const handleEnroll = async (member) => {
    setEnrollingId(member.id);
    try {
      const { data } = await membersApi.enroll(member.id);
      toast.success(data.detail || 'Fingerprint template queued for device sync.');
      setRefreshKey((current) => current + 1);
    } catch (enrollError) {
      toast.error(getErrorMessage(enrollError, 'Could not queue enrollment.'));
    } finally {
      setEnrollingId(null);
    }
  };

  const handleDelete = async () => {
    if (!confirmMember) return;
    setDeleting(true);
    try {
      await membersApi.remove(confirmMember.id);
      toast.success(`${confirmMember.full_name} was removed.`);
      setConfirmMember(null);
      if (members.length === 1 && page > 1) setPage((current) => current - 1);
      else setRefreshKey((current) => current + 1);
    } catch (deleteError) {
      toast.error(getErrorMessage(deleteError, 'Could not delete this member.'));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="page">
      <PageHeader
        eyebrow="People & access"
        title="Members & visitors"
        subtitle="Registered family, staff and pre-enrolled visitors. Fingerprints stay on the device."
        actions={
          <button type="button" className="btn btn-primary" onClick={openCreate}>
            <Plus size={16} /> Register person
          </button>
        }
      />

      <ErrorBanner message={error} onRetry={loadMembers} />

      <div className="toolbar">
        <div className="segmented" role="tablist" aria-label="Filter by role">
          {ROLE_TABS.map((tab) => (
            <button
              key={tab.value || 'all'}
              type="button"
              className={roleFilter === tab.value ? 'active' : ''}
              onClick={() => {
                setRoleFilter(tab.value);
                setPage(1);
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="toolbar-right">
          <div className="search-wrap">
            <Search size={15} />
            <input
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Search name, username, email…"
              aria-label="Search people"
            />
          </div>
          <span className="result-count">{count} people</span>
        </div>
      </div>

      {loading ? (
        <div className="members-grid">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="member-skeleton" />
          ))}
        </div>
      ) : members.length ? (
        <>
          <div className="members-grid">
            {members.map((member) => (
              <MemberCard
                key={member.id}
                member={member}
                onEdit={openEdit}
                onDelete={setConfirmMember}
                onEnroll={handleEnroll}
                enrolling={enrollingId === member.id}
              />
            ))}
          </div>
          <Pagination
            page={page}
            count={count}
            pageSize={PAGE_SIZE}
            onPageChange={setPage}
            loading={loading}
          />
        </>
      ) : (
        <div className="card">
          <EmptyState
            icon={search || roleFilter ? Search : UserPlus}
            title={search || roleFilter ? 'No matching people' : 'No one registered yet'}
            message={
              search || roleFilter
                ? 'Try a different search or role filter.'
                : 'Register a family member, staff member or pre-enrolled visitor to get started.'
            }
            action={
              !search && !roleFilter ? (
                <button type="button" className="btn btn-primary" onClick={openCreate}>
                  <Users size={16} /> Register the first person
                </button>
              ) : null
            }
          />
        </div>
      )}

      <MemberForm
        open={formOpen}
        member={editingMember}
        onClose={() => setFormOpen(false)}
        onSaved={handleSaved}
      />

      <ConfirmDialog
        open={Boolean(confirmMember)}
        title="Delete this profile?"
        message={
          confirmMember
            ? `${confirmMember.full_name} (@${confirmMember.username}) will be removed permanently, along with their fingerprint templates. This cannot be undone.`
            : ''
        }
        confirmLabel="Delete profile"
        onConfirm={handleDelete}
        onCancel={() => setConfirmMember(null)}
        loading={deleting}
      />
    </div>
  );
}
