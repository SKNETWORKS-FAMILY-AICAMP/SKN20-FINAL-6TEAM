import React, { useState } from 'react';
import type { DocumentTypeField } from '../lib/documentApi';

export const inputClass =
  'w-full px-3 py-2 text-sm border border-gray-300 rounded-lg outline-none transition-colors focus:border-blue-500 focus:ring-1 focus:ring-blue-500';

export function useDocumentForm() {
  const [formValues, setFormValues] = useState<Record<string, string>>({});

  const initFormValues = (fields: DocumentTypeField[]) => {
    const initial: Record<string, string> = {};
    for (const f of fields) {
      initial[f.name] = '';
    }
    setFormValues(initial);
  };

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>,
  ) => {
    const { name, value } = e.target;
    setFormValues((prev) => ({ ...prev, [name]: value }));
  };

  const isValid = (fields: DocumentTypeField[]): boolean =>
    fields
      .filter((f) => f.required)
      .every((f) => {
        const val = formValues[f.name];
        return val !== undefined && val.trim() !== '';
      });

  const renderField = (field: DocumentTypeField) => {
    const value = formValues[field.name] ?? '';

    if (field.field_type === 'textarea') {
      return (
        <textarea
          name={field.name}
          value={value}
          onChange={handleChange}
          placeholder={field.placeholder}
          rows={3}
          className={`${inputClass} resize-none`}
        />
      );
    }

    if (field.field_type === 'select' && field.options) {
      return (
        <select name={field.name} value={value} onChange={handleChange} className={inputClass}>
          <option value="">선택하세요</option>
          {field.options.map((opt) => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      );
    }

    const inputType =
      field.field_type === 'number' ? 'number' : field.field_type === 'date' ? 'date' : 'text';

    return (
      <input
        name={field.name}
        type={inputType}
        value={value}
        onChange={handleChange}
        placeholder={field.placeholder}
        className={inputClass}
      />
    );
  };

  return { formValues, setFormValues, initFormValues, handleChange, isValid, renderField };
}
