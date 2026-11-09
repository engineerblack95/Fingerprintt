import { useEffect, useRef, useState } from 'react';
import { ImageUp, Loader2, UserPlus, X } from 'lucide-react';

import { getErrorMessage, getFieldErrors, membersApi } from '../api/client';
import { useToast } from '../context/ToastContext';
import { Modal } from './Modal';
import { ErrorBanner } from './ErrorBanner';

const EMPTY_FORM = {
  username: '',
  full_name: '',
  phone_number: '',
  email: '',
  role: 'MEMBER',
  is_active: true,
};

function firstError(value) {
  if (!value) return '';
  if (Array.isArray(value)) return value[0] || '';
  return String(value);
}

export function MemberForm({ open, member, onClose, onSaved }) {
  const toast = useToast();
  const fileInputRef = useRef(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [errors, setErrors] = useState({});
  const [generalError, setGeneralError] = useState('');
  const [saving, setSaving] = useState(false);
  const isEdit = Boolean(member);

  useEffect(() => {
    if (!open) return;
    setForm(
      member
        ? {
            username: member.username || '',
            full_name: member.full_name || '',
            phone_number: member.phone_number || '',
            email: member.email || '',
            role: member.role || 'MEMBER',
            is_active: Boolean(member.is_active),
          }
        : EMPTY_FORM,
    );
    setFile(null);
    setPreview(member?.photo_url || null);
    setErrors({});
    setGeneralError('');
    setSaving(false);
  }, [open, member]);

  useEffect(() => {
    if (!preview || !preview.startsWith('blob:')) return undefined;
    return () => URL.revokeObjectURL(preview);
  }, [preview]);

  const handleChange = (event) => {
    const { name, value, type, checked } = event.target;
    setForm((current) => ({ ...current, [name]: type === 'checkbox' ? checked : value }));
  };

  const handleFile = (event) => {
    const selected = event.target.files?.[0];
    if (!selected) return;
    if (selected.size > 5 * 1024 * 1024) {
      setGeneralError('Photo must be smaller than 5 MB.');
      event.target.value = '';
      return;
    }
    setFile(selected);
    setPreview(URL.createObjectURL(selected));
    setErrors((current) => ({ ...current, photo: undefined }));
    setGeneralError('');
  };

  const clearPhoto = () => {
    setFile(null);
    setPreview(member?.photo_url || null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const validate = () => {
    const next = {};
    if (!form.username.trim()) next.username = 'Username is required.';
    else if (form.username.trim().length < 3) next.username = 'At least 3 characters.';
    if (!form.full_name.trim()) next.full_name = 'Full name is required.';
    if (!form.email.trim()) next.email = 'Email is required.';
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) {
      next.email = 'Enter a valid email address.';
    }
    if (!form.phone_number.trim()) next.phone_number = 'Phone number is required.';
    else if (form.phone_number.replace(/[^0-9]/g, '').length < 7) {
      next.phone_number = 'Enter a valid phone number.';
    }
    if (!isEdit && !file) next.photo = 'A profile photo is required.';
    return next;
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setGeneralError('');
    const clientErrors = validate();
    if (Object.keys(clientErrors).length) {
      setErrors(clientErrors);
      return;
    }

    const payload = new FormData();
    payload.append('username', form.username.trim());
    payload.append('full_name', form.full_name.trim());
    payload.append('phone_number', form.phone_number.trim());
    payload.append('email', form.email.trim());
    payload.append('role', form.role);
    payload.append('is_active', String(form.is_active));
    if (file) payload.append('photo', file);

    setSaving(true);
    try {
      const response = isEdit
        ? await membersApi.update(member.id, payload)
        : await membersApi.create(payload);
      toast.success(isEdit ? 'Member profile updated.' : 'New person registered successfully.');
      onSaved?.(response.data, { created: !isEdit });
      onClose?.();
    } catch (error) {
      const fieldErrors = getFieldErrors(error);
      setErrors(fieldErrors);
      setGeneralError(getErrorMessage(error, 'Could not save this profile.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      title={isEdit ? 'Edit profile' : 'Register a new person'}
      subtitle={
        isEdit
          ? 'Update the profile, role or access state.'
          : 'Add a family member or pre-enroll a special visitor.'
      }
      onClose={saving ? () => {} : onClose}
      size="lg"
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button type="submit" form="member-form" className="btn btn-primary" disabled={saving}>
            {saving ? <Loader2 size={16} className="spin" /> : <UserPlus size={16} />}
            {saving ? 'Saving…' : isEdit ? 'Save changes' : 'Register person'}
          </button>
        </>
      }
    >
      <ErrorBanner message={generalError} />

      <form id="member-form" className="member-form" onSubmit={handleSubmit} noValidate>
        <div className="photo-uploader">
          <div className="photo-preview">
            {preview ? (
              <img src={preview} alt="Profile preview" />
            ) : (
              <ImageUp size={26} />
            )}
          </div>
          <div className="photo-uploader-copy">
            <strong>{isEdit ? 'Profile photo' : 'Profile photo *'}</strong>
            <p>JPEG, PNG or WEBP · maximum 5 MB. Uploaded at registration — no camera is used.</p>
            <div className="photo-actions">
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => fileInputRef.current?.click()}
              >
                <ImageUp size={14} />
                {file ? 'Choose another' : preview ? 'Replace photo' : 'Upload photo'}
              </button>
              {file ? (
                <button type="button" className="btn btn-ghost btn-sm" onClick={clearPhoto}>
                  <X size={14} /> Undo
                </button>
              ) : null}
            </div>
            {errors.photo ? <span className="field-error">{firstError(errors.photo)}</span> : null}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="sr-only"
            onChange={handleFile}
          />
        </div>

        <div className="form-grid">
          <label className="field">
            <span className="field-label">Full name *</span>
            <input
              className={`input ${errors.full_name ? 'input-error' : ''}`}
              name="full_name"
              value={form.full_name}
              onChange={handleChange}
              placeholder="Amina Keza"
              autoComplete="name"
            />
            {errors.full_name ? <span className="field-error">{firstError(errors.full_name)}</span> : null}
          </label>

          <label className="field">
            <span className="field-label">Username *</span>
            <input
              className={`input ${errors.username ? 'input-error' : ''}`}
              name="username"
              value={form.username}
              onChange={handleChange}
              placeholder="amina.k"
              autoComplete="off"
            />
            {errors.username ? <span className="field-error">{firstError(errors.username)}</span> : null}
          </label>

          <label className="field">
            <span className="field-label">Email *</span>
            <input
              className={`input ${errors.email ? 'input-error' : ''}`}
              name="email"
              type="email"
              value={form.email}
              onChange={handleChange}
              placeholder="amina@example.com"
              autoComplete="email"
            />
            {errors.email ? <span className="field-error">{firstError(errors.email)}</span> : null}
          </label>

          <label className="field">
            <span className="field-label">Phone number *</span>
            <input
              className={`input ${errors.phone_number ? 'input-error' : ''}`}
              name="phone_number"
              value={form.phone_number}
              onChange={handleChange}
              placeholder="+250 788 000 000"
              autoComplete="tel"
            />
            {errors.phone_number ? (
              <span className="field-error">{firstError(errors.phone_number)}</span>
            ) : null}
          </label>

          <label className="field">
            <span className="field-label">Identity category *</span>
            <select className="select" name="role" value={form.role} onChange={handleChange}>
              <option value="MEMBER">Registered member — family / staff</option>
              <option value="VISITOR">Registered visitor — pre-enrolled</option>
            </select>
            {errors.role ? <span className="field-error">{firstError(errors.role)}</span> : null}
          </label>

          <label className="field field-switch">
            <span>
              <span className="field-label">Access active</span>
              <span className="field-hint">Inactive profiles cannot enter.</span>
            </span>
            <span className={`switch ${form.is_active ? 'on' : ''}`}>
              <input
                type="checkbox"
                name="is_active"
                checked={form.is_active}
                onChange={handleChange}
              />
              <span className="switch-track" />
            </span>
          </label>
        </div>

        {!isEdit ? (
          <p className="form-note">
            After registering, use <strong>Enroll</strong> to queue a fingerprint template. The
            template is captured and matched on the device — never uploaded as an image.
          </p>
        ) : null}
      </form>
    </Modal>
  );
}
