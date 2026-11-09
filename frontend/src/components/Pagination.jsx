import { ChevronLeft, ChevronRight } from 'lucide-react';

export function Pagination({ page, count, pageSize, onPageChange, loading = false }) {
  const totalPages = Math.max(1, Math.ceil(count / pageSize));
  if (!count) return null;

  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, count);

  const pages = [];
  const windowStart = Math.max(1, Math.min(page - 2, totalPages - 4));
  const windowEnd = Math.min(totalPages, windowStart + 4);
  for (let current = windowStart; current <= windowEnd; current += 1) {
    pages.push(current);
  }

  return (
    <div className="pagination">
      <span className="pagination-summary">
        Showing <strong>{start}</strong>–<strong>{end}</strong> of <strong>{count}</strong>
      </span>
      <div className="pagination-controls">
        <button
          type="button"
          className="btn-icon"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1 || loading}
          aria-label="Previous page"
        >
          <ChevronLeft size={18} />
        </button>
        {pages.map((current) => (
          <button
            key={current}
            type="button"
            className={`page-chip ${current === page ? 'active' : ''}`}
            onClick={() => onPageChange(current)}
            disabled={loading}
          >
            {current}
          </button>
        ))}
        <button
          type="button"
          className="btn-icon"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages || loading}
          aria-label="Next page"
        >
          <ChevronRight size={18} />
        </button>
      </div>
    </div>
  );
}
