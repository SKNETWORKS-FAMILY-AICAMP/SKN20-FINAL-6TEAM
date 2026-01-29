# FORM.md - 폼 아키텍처 가이드라인

> **Bizi 프로젝트 폼(Form) 개발 표준 문서**
> 이 문서는 React + TypeScript 기반 폼 컴포넌트의 일관된 아키텍처와 코드 품질을 보장하기 위한 필수 가이드라인입니다.

## 📋 목차
1. [핵심 원칙](#핵심-원칙)
2. [아키텍처 레이어](#아키텍처-레이어)
3. [디렉토리 구조](#디렉토리-구조)
4. [TypeScript 타입 정의](#typescript-타입-정의)
5. [커스텀 훅 패턴](#커스텀-훅-패턴)
6. [폼 컴포넌트 구조](#폼-컴포넌트-구조)
7. [검증(Validation) 패턴](#검증-패턴)
8. [에러 처리 및 표시](#에러-처리-및-표시)
9. [상태 관리](#상태-관리)
10. [재사용 가능한 폼 컴포넌트](#재사용-가능한-폼-컴포넌트)
11. [접근성(Accessibility)](#접근성)
12. [실전 예제](#실전-예제)

---

## 핵심 원칙

### 1. 관심사의 분리 (Separation of Concerns)
```
┌─────────────────────────────────────────────────┐
│  UI Layer (Components)                          │
│  - 렌더링, 사용자 인터랙션, 접근성               │
└────────────────┬────────────────────────────────┘
                 │ Props & Callbacks
┌────────────────▼────────────────────────────────┐
│  Business Logic Layer (Custom Hooks)            │
│  - 상태 관리, 검증, API 호출, 부수 효과          │
└────────────────┬────────────────────────────────┘
                 │ Type Safety
┌────────────────▼────────────────────────────────┐
│  Type Layer (TypeScript Definitions)            │
│  - 인터페이스, 타입, 제네릭                      │
└─────────────────────────────────────────────────┘
```

### 2. 타입 안정성 (Type Safety)
- **모든 폼 데이터에 명시적 인터페이스 정의 필수**
- `any` 타입 사용 금지 (불가피한 경우 주석으로 이유 명시)
- 제네릭을 활용한 재사용 가능한 폼 로직 구현

### 3. 재사용성 (Reusability)
- Atomic Design 패턴 기반 컴포넌트 설계
- 설정 가능한 검증 규칙 및 포매터
- 컴포지션(Composition)을 통한 복잡한 폼 구성

### 4. 접근성 우선 (Accessibility First)
- 모든 입력 필드에 `<label>` 또는 `aria-label` 필수
- 키보드 네비게이션 지원
- 에러 메시지는 스크린 리더 접근 가능하도록 `aria-describedby` 활용

---

## 아키텍처 레이어

### Layer 1: Type Definitions (타입 정의)
**위치**: `src/types/forms/`

모든 폼 관련 타입을 중앙 집중화하여 관리합니다.

```typescript
// src/types/forms/company.types.ts
export interface CompanyFormData {
  com_name: string;
  biz_num: string;
  addr: string;
  open_date: string;
  biz_code: string;
}

export interface CompanyFormErrors {
  com_name?: string;
  biz_num?: string;
  addr?: string;
  open_date?: string;
  biz_code?: string;
}

export interface CompanyFormState {
  data: CompanyFormData;
  errors: CompanyFormErrors;
  touched: Record<keyof CompanyFormData, boolean>;
  isSubmitting: boolean;
  isValid: boolean;
}
```

### Layer 2: Custom Hooks (비즈니스 로직)
**위치**: `src/hooks/forms/`

폼의 모든 비즈니스 로직을 캡슐화합니다.

```typescript
// src/hooks/forms/useCompanyForm.ts
import { useState, useCallback } from 'react';
import type { CompanyFormData, CompanyFormErrors, CompanyFormState } from '@/types/forms/company.types';

export const useCompanyForm = (initialData?: Partial<CompanyFormData>) => {
  const [formState, setFormState] = useState<CompanyFormState>({
    data: {
      com_name: initialData?.com_name || '',
      biz_num: initialData?.biz_num || '',
      addr: initialData?.addr || '',
      open_date: initialData?.open_date || '',
      biz_code: initialData?.biz_code || 'B001',
    },
    errors: {},
    touched: {},
    isSubmitting: false,
    isValid: false,
  });

  const validateField = useCallback((name: keyof CompanyFormData, value: string): string | undefined => {
    // 검증 로직
  }, []);

  const handleChange = useCallback((name: keyof CompanyFormData, value: string) => {
    // 변경 처리 로직
  }, []);

  const handleSubmit = useCallback(async () => {
    // 제출 처리 로직
  }, []);

  return {
    formData: formState.data,
    errors: formState.errors,
    touched: formState.touched,
    isSubmitting: formState.isSubmitting,
    isValid: formState.isValid,
    handleChange,
    handleBlur,
    handleSubmit,
    resetForm,
  };
};
```

### Layer 3: UI Components (프레젠테이션)
**위치**: `src/components/forms/` 또는 `src/pages/`

훅에서 반환된 값을 사용하여 UI를 렌더링합니다.

```typescript
// src/components/forms/CompanyForm.tsx
import React from 'react';
import { useCompanyForm } from '@/hooks/forms/useCompanyForm';
import { FormInput, FormSelect, FormError } from '@/components/forms/common';

export const CompanyForm: React.FC = () => {
  const {
    formData,
    errors,
    touched,
    isSubmitting,
    handleChange,
    handleBlur,
    handleSubmit,
  } = useCompanyForm();

  return (
    <form onSubmit={handleSubmit}>
      <FormInput
        label="회사명"
        name="com_name"
        value={formData.com_name}
        error={touched.com_name ? errors.com_name : undefined}
        onChange={(e) => handleChange('com_name', e.target.value)}
        onBlur={() => handleBlur('com_name')}
        required
      />
      {/* 추가 필드들 */}
    </form>
  );
};
```

---

## 디렉토리 구조

```
frontend/src/
├── types/
│   └── forms/                    # 폼 관련 타입 정의
│       ├── company.types.ts      # 기업 폼 타입
│       ├── profile.types.ts      # 프로필 폼 타입
│       ├── schedule.types.ts     # 일정 폼 타입
│       └── common.types.ts       # 공통 폼 타입
│
├── hooks/
│   └── forms/                    # 폼 로직 커스텀 훅
│       ├── useCompanyForm.ts
│       ├── useProfileForm.ts
│       ├── useScheduleForm.ts
│       └── useFormValidation.ts  # 공통 검증 훅
│
├── components/
│   └── forms/
│       ├── common/               # 재사용 가능한 폼 컴포넌트
│       │   ├── FormInput.tsx
│       │   ├── FormSelect.tsx
│       │   ├── FormTextarea.tsx
│       │   ├── FormCheckbox.tsx
│       │   ├── FormDatePicker.tsx
│       │   ├── FormError.tsx
│       │   └── FormLabel.tsx
│       │
│       ├── CompanyForm.tsx       # 도메인별 폼 컴포넌트
│       ├── ProfileForm.tsx
│       └── ScheduleForm.tsx
│
└── utils/
    └── validation/               # 검증 유틸리티
        ├── validators.ts         # 재사용 가능한 검증 함수
        ├── formatters.ts         # 데이터 포매터
        └── constants.ts          # 검증 관련 상수
```

---

## TypeScript 타입 정의

### 1. 기본 폼 타입 구조

```typescript
// src/types/forms/common.types.ts

/**
 * 폼 필드의 기본 타입
 */
export type FormFieldValue = string | number | boolean | Date | null;

/**
 * 폼 필드 에러 타입
 */
export type FormFieldError = string | undefined;

/**
 * 제네릭 폼 상태
 */
export interface FormState<T> {
  /** 폼 데이터 */
  data: T;
  /** 필드별 에러 메시지 */
  errors: Partial<Record<keyof T, string>>;
  /** 필드 터치 여부 (포커스를 받았다가 잃은 필드) */
  touched: Partial<Record<keyof T, boolean>>;
  /** 제출 진행 중 여부 */
  isSubmitting: boolean;
  /** 폼 전체 유효성 */
  isValid: boolean;
  /** 폼 수정 여부 */
  isDirty: boolean;
}

/**
 * 검증 규칙 타입
 */
export interface ValidationRule<T = FormFieldValue> {
  /** 검증 함수 */
  validate: (value: T) => boolean | Promise<boolean>;
  /** 에러 메시지 */
  message: string;
}

/**
 * 필드 설정 타입
 */
export interface FieldConfig<T = FormFieldValue> {
  /** 초기값 */
  initialValue: T;
  /** 필수 여부 */
  required?: boolean;
  /** 검증 규칙 배열 */
  rules?: ValidationRule<T>[];
  /** 값 변환 함수 (저장 전) */
  transform?: (value: T) => T;
}
```

### 2. 도메인별 폼 타입 예시

```typescript
// src/types/forms/company.types.ts
import type { FormState } from './common.types';

/**
 * 기업 등록/수정 폼 데이터
 */
export interface CompanyFormData {
  /** 회사명 (필수) */
  com_name: string;
  /** 사업자등록번호 (형식: 000-00-00000) */
  biz_num: string;
  /** 주소 */
  addr: string;
  /** 개업일 (ISO 8601 날짜) */
  open_date: string;
  /** 업종 코드 */
  biz_code: string;
  /** 사업자등록증 파일 경로 */
  file_path?: string;
}

/**
 * 기업 폼 상태
 */
export type CompanyFormState = FormState<CompanyFormData>;

/**
 * 기업 폼 제출 데이터 (API 요청용)
 */
export interface CompanyFormSubmitData extends Omit<CompanyFormData, 'open_date'> {
  /** 개업일 (ISO 8601 DateTime) */
  open_date: string | null;
}
```

```typescript
// src/types/forms/profile.types.ts
import type { FormState } from './common.types';

/**
 * 프로필 수정 폼 데이터
 */
export interface ProfileFormData {
  /** 사용자 이름 */
  username: string;
  /** 사용자 유형 코드 */
  type_code: 'U001' | 'U002' | 'U003';
  /** 생년월일 (선택) */
  birth?: string;
}

/**
 * 프로필 폼 상태
 */
export type ProfileFormState = FormState<ProfileFormData>;
```

### 3. 제네릭 폼 훅 타입

```typescript
// src/types/forms/hooks.types.ts

/**
 * 폼 훅 반환 타입
 */
export interface UseFormReturn<T> {
  /** 현재 폼 데이터 */
  formData: T;
  /** 필드별 에러 */
  errors: Partial<Record<keyof T, string>>;
  /** 필드 터치 상태 */
  touched: Partial<Record<keyof T, boolean>>;
  /** 제출 중 여부 */
  isSubmitting: boolean;
  /** 폼 유효성 */
  isValid: boolean;
  /** 폼 수정 여부 */
  isDirty: boolean;
  /** 필드 값 변경 핸들러 */
  handleChange: <K extends keyof T>(name: K, value: T[K]) => void;
  /** 필드 블러 핸들러 */
  handleBlur: (name: keyof T) => void;
  /** 폼 제출 핸들러 */
  handleSubmit: (e?: React.FormEvent) => Promise<void>;
  /** 폼 리셋 */
  resetForm: () => void;
  /** 특정 필드 에러 설정 */
  setFieldError: (name: keyof T, error: string) => void;
  /** 특정 필드 값 설정 */
  setFieldValue: <K extends keyof T>(name: K, value: T[K]) => void;
}

/**
 * 폼 훅 옵션
 */
export interface UseFormOptions<T> {
  /** 초기 데이터 */
  initialValues: T;
  /** 검증 함수 */
  validate?: (values: T) => Partial<Record<keyof T, string>>;
  /** 제출 핸들러 */
  onSubmit: (values: T) => Promise<void>;
  /** 제출 성공 콜백 */
  onSuccess?: () => void;
  /** 제출 실패 콜백 */
  onError?: (error: Error) => void;
}
```

---

## 커스텀 훅 패턴

### 1. 기본 폼 훅 구현

```typescript
// src/hooks/forms/useForm.ts
import { useState, useCallback, useMemo } from 'react';
import type { UseFormOptions, UseFormReturn } from '@/types/forms/hooks.types';

/**
 * 제네릭 폼 훅
 * @template T - 폼 데이터 타입
 */
export function useForm<T extends Record<string, any>>(
  options: UseFormOptions<T>
): UseFormReturn<T> {
  const { initialValues, validate, onSubmit, onSuccess, onError } = options;

  const [formData, setFormData] = useState<T>(initialValues);
  const [errors, setErrors] = useState<Partial<Record<keyof T, string>>>({});
  const [touched, setTouched] = useState<Partial<Record<keyof T, boolean>>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  // 폼 수정 여부
  const isDirty = useMemo(() => {
    return JSON.stringify(formData) !== JSON.stringify(initialValues);
  }, [formData, initialValues]);

  // 폼 유효성
  const isValid = useMemo(() => {
    return Object.keys(errors).length === 0;
  }, [errors]);

  // 필드 값 변경
  const handleChange = useCallback(<K extends keyof T>(name: K, value: T[K]) => {
    setFormData((prev) => ({ ...prev, [name]: value }));

    // 터치된 필드는 즉시 검증
    if (touched[name] && validate) {
      const validationErrors = validate({ ...formData, [name]: value });
      setErrors((prev) => ({
        ...prev,
        [name]: validationErrors[name],
      }));
    }
  }, [formData, touched, validate]);

  // 필드 블러
  const handleBlur = useCallback((name: keyof T) => {
    setTouched((prev) => ({ ...prev, [name]: true }));

    // 블러 시 해당 필드 검증
    if (validate) {
      const validationErrors = validate(formData);
      setErrors((prev) => ({
        ...prev,
        [name]: validationErrors[name],
      }));
    }
  }, [formData, validate]);

  // 폼 제출
  const handleSubmit = useCallback(async (e?: React.FormEvent) => {
    if (e) {
      e.preventDefault();
    }

    // 모든 필드를 터치 상태로 변경
    const allTouched = Object.keys(formData).reduce(
      (acc, key) => ({ ...acc, [key]: true }),
      {} as Record<keyof T, boolean>
    );
    setTouched(allTouched);

    // 전체 검증
    if (validate) {
      const validationErrors = validate(formData);
      setErrors(validationErrors);

      if (Object.keys(validationErrors).length > 0) {
        return;
      }
    }

    setIsSubmitting(true);

    try {
      await onSubmit(formData);
      onSuccess?.();
    } catch (error) {
      onError?.(error as Error);
    } finally {
      setIsSubmitting(false);
    }
  }, [formData, validate, onSubmit, onSuccess, onError]);

  // 폼 리셋
  const resetForm = useCallback(() => {
    setFormData(initialValues);
    setErrors({});
    setTouched({});
    setIsSubmitting(false);
  }, [initialValues]);

  // 특정 필드 에러 설정
  const setFieldError = useCallback((name: keyof T, error: string) => {
    setErrors((prev) => ({ ...prev, [name]: error }));
  }, []);

  // 특정 필드 값 설정
  const setFieldValue = useCallback(<K extends keyof T>(name: K, value: T[K]) => {
    setFormData((prev) => ({ ...prev, [name]: value }));
  }, []);

  return {
    formData,
    errors,
    touched,
    isSubmitting,
    isValid,
    isDirty,
    handleChange,
    handleBlur,
    handleSubmit,
    resetForm,
    setFieldError,
    setFieldValue,
  };
}
```

### 2. 도메인별 폼 훅 예시

```typescript
// src/hooks/forms/useCompanyForm.ts
import { useCallback } from 'react';
import { useForm } from './useForm';
import { validateCompanyForm } from '@/utils/validation/validators';
import api from '@/lib/api';
import type { CompanyFormData, CompanyFormSubmitData } from '@/types/forms/company.types';

interface UseCompanyFormOptions {
  /** 수정 모드일 때 기업 ID */
  companyId?: number;
  /** 초기 데이터 */
  initialData?: Partial<CompanyFormData>;
  /** 성공 콜백 */
  onSuccess?: () => void;
  /** 에러 콜백 */
  onError?: (error: Error) => void;
}

/**
 * 기업 등록/수정 폼 훅
 */
export function useCompanyForm(options: UseCompanyFormOptions = {}) {
  const { companyId, initialData, onSuccess, onError } = options;

  const isEditMode = Boolean(companyId);

  // 제출 핸들러
  const handleSubmit = useCallback(async (values: CompanyFormData) => {
    // API 요청 데이터 변환
    const submitData: CompanyFormSubmitData = {
      ...values,
      open_date: values.open_date ? new Date(values.open_date).toISOString() : null,
    };

    if (isEditMode) {
      await api.put(`/companies/${companyId}`, submitData);
    } else {
      await api.post('/companies', submitData);
    }
  }, [companyId, isEditMode]);

  const formHook = useForm<CompanyFormData>({
    initialValues: {
      com_name: initialData?.com_name || '',
      biz_num: initialData?.biz_num || '',
      addr: initialData?.addr || '',
      open_date: initialData?.open_date || '',
      biz_code: initialData?.biz_code || 'B001',
      file_path: initialData?.file_path || '',
    },
    validate: validateCompanyForm,
    onSubmit: handleSubmit,
    onSuccess,
    onError,
  });

  return {
    ...formHook,
    isEditMode,
  };
}
```

### 3. API 통합 폼 훅 (TanStack Query 패턴)

```typescript
// src/hooks/forms/useCompanyFormWithQuery.ts
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from './useForm';
import { validateCompanyForm } from '@/utils/validation/validators';
import api from '@/lib/api';
import type { CompanyFormData } from '@/types/forms/company.types';

/**
 * TanStack Query를 활용한 기업 폼 훅
 */
export function useCompanyFormWithQuery(companyId?: number) {
  const queryClient = useQueryClient();

  // Mutation 정의
  const createMutation = useMutation({
    mutationFn: async (data: CompanyFormData) => {
      const response = await api.post('/companies', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['companies'] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: async (data: CompanyFormData) => {
      const response = await api.put(`/companies/${companyId}`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['companies'] });
      queryClient.invalidateQueries({ queryKey: ['company', companyId] });
    },
  });

  const formHook = useForm<CompanyFormData>({
    initialValues: {
      com_name: '',
      biz_num: '',
      addr: '',
      open_date: '',
      biz_code: 'B001',
    },
    validate: validateCompanyForm,
    onSubmit: async (values) => {
      if (companyId) {
        await updateMutation.mutateAsync(values);
      } else {
        await createMutation.mutateAsync(values);
      }
    },
  });

  return {
    ...formHook,
    isLoading: createMutation.isPending || updateMutation.isPending,
    isSuccess: createMutation.isSuccess || updateMutation.isSuccess,
    error: createMutation.error || updateMutation.error,
  };
}
```

---

## 폼 컴포넌트 구조

### 1. Atomic 폼 컴포넌트 (재사용 가능)

```typescript
// src/components/forms/common/FormInput.tsx
import React from 'react';
import { Input } from '@material-tailwind/react';
import { FormLabel } from './FormLabel';
import { FormError } from './FormError';

interface FormInputProps {
  /** 필드 이름 (고유 ID로도 사용) */
  name: string;
  /** 라벨 텍스트 */
  label: string;
  /** 입력 타입 */
  type?: 'text' | 'email' | 'password' | 'tel' | 'url' | 'number';
  /** 현재 값 */
  value: string | number;
  /** 변경 핸들러 */
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  /** 블러 핸들러 */
  onBlur?: (e: React.FocusEvent<HTMLInputElement>) => void;
  /** 에러 메시지 */
  error?: string;
  /** 플레이스홀더 */
  placeholder?: string;
  /** 필수 여부 */
  required?: boolean;
  /** 비활성화 여부 */
  disabled?: boolean;
  /** 자동완성 */
  autoComplete?: string;
  /** 최대 길이 */
  maxLength?: number;
  /** 추가 CSS 클래스 */
  className?: string;
}

/**
 * 재사용 가능한 폼 입력 컴포넌트
 * - 라벨, 입력 필드, 에러 메시지를 통합
 * - 접근성 속성 자동 설정
 */
export const FormInput: React.FC<FormInputProps> = ({
  name,
  label,
  type = 'text',
  value,
  onChange,
  onBlur,
  error,
  placeholder,
  required = false,
  disabled = false,
  autoComplete,
  maxLength,
  className,
}) => {
  const inputId = `form-input-${name}`;
  const errorId = `form-error-${name}`;
  const hasError = Boolean(error);

  return (
    <div className={className}>
      <FormLabel htmlFor={inputId} required={required}>
        {label}
      </FormLabel>

      <Input
        id={inputId}
        name={name}
        type={type}
        value={value}
        onChange={onChange}
        onBlur={onBlur}
        placeholder={placeholder}
        disabled={disabled}
        autoComplete={autoComplete}
        maxLength={maxLength}
        className={`!border-gray-300 ${hasError ? '!border-red-500' : ''}`}
        labelProps={{ className: 'hidden' }}
        aria-invalid={hasError}
        aria-describedby={hasError ? errorId : undefined}
        aria-required={required}
      />

      {hasError && <FormError id={errorId} message={error} />}
    </div>
  );
};
```

```typescript
// src/components/forms/common/FormLabel.tsx
import React from 'react';
import { Typography } from '@material-tailwind/react';

interface FormLabelProps {
  /** label의 for 속성 */
  htmlFor: string;
  /** 라벨 텍스트 */
  children: React.ReactNode;
  /** 필수 여부 */
  required?: boolean;
  /** 추가 CSS 클래스 */
  className?: string;
}

/**
 * 폼 라벨 컴포넌트
 * - 필수 필드 표시 (*) 자동 추가
 */
export const FormLabel: React.FC<FormLabelProps> = ({
  htmlFor,
  children,
  required = false,
  className = '',
}) => {
  return (
    <label htmlFor={htmlFor} className={`block mb-1 ${className}`}>
      <Typography variant="small" color="gray" className="font-medium">
        {children}
        {required && <span className="text-red-500 ml-1" aria-label="필수 항목">*</span>}
      </Typography>
    </label>
  );
};
```

```typescript
// src/components/forms/common/FormError.tsx
import React from 'react';
import { Typography } from '@material-tailwind/react';
import { ExclamationCircleIcon } from '@heroicons/react/24/outline';

interface FormErrorProps {
  /** 에러 메시지 ID (aria-describedby 연결용) */
  id?: string;
  /** 에러 메시지 */
  message: string;
  /** 추가 CSS 클래스 */
  className?: string;
}

/**
 * 폼 에러 메시지 컴포넌트
 * - 스크린 리더 접근성 지원
 */
export const FormError: React.FC<FormErrorProps> = ({
  id,
  message,
  className = '',
}) => {
  return (
    <div
      id={id}
      role="alert"
      aria-live="polite"
      className={`flex items-center gap-1 mt-1 ${className}`}
    >
      <ExclamationCircleIcon className="h-4 w-4 text-red-500 flex-shrink-0" />
      <Typography variant="small" color="red" className="font-normal">
        {message}
      </Typography>
    </div>
  );
};
```

```typescript
// src/components/forms/common/FormSelect.tsx
import React from 'react';
import { Select, Option } from '@material-tailwind/react';
import { FormLabel } from './FormLabel';
import { FormError } from './FormError';

interface FormSelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

interface FormSelectProps {
  /** 필드 이름 */
  name: string;
  /** 라벨 텍스트 */
  label: string;
  /** 현재 선택된 값 */
  value: string;
  /** 변경 핸들러 */
  onChange: (value: string) => void;
  /** 블러 핸들러 */
  onBlur?: () => void;
  /** 선택 옵션 배열 */
  options: FormSelectOption[];
  /** 에러 메시지 */
  error?: string;
  /** 필수 여부 */
  required?: boolean;
  /** 비활성화 여부 */
  disabled?: boolean;
  /** 플레이스홀더 */
  placeholder?: string;
  /** 추가 CSS 클래스 */
  className?: string;
}

/**
 * 재사용 가능한 폼 셀렉트 컴포넌트
 */
export const FormSelect: React.FC<FormSelectProps> = ({
  name,
  label,
  value,
  onChange,
  onBlur,
  options,
  error,
  required = false,
  disabled = false,
  placeholder,
  className,
}) => {
  const selectId = `form-select-${name}`;
  const errorId = `form-error-${name}`;
  const hasError = Boolean(error);

  return (
    <div className={className}>
      <FormLabel htmlFor={selectId} required={required}>
        {label}
      </FormLabel>

      <Select
        id={selectId}
        name={name}
        value={value}
        onChange={(val) => onChange(val || '')}
        onBlur={onBlur}
        disabled={disabled}
        className={`!border-gray-300 ${hasError ? '!border-red-500' : ''}`}
        labelProps={{ className: 'hidden' }}
        aria-invalid={hasError}
        aria-describedby={hasError ? errorId : undefined}
        aria-required={required}
      >
        {placeholder && (
          <Option value="" disabled>
            {placeholder}
          </Option>
        )}
        {options.map((option) => (
          <Option
            key={option.value}
            value={option.value}
            disabled={option.disabled}
          >
            {option.label}
          </Option>
        ))}
      </Select>

      {hasError && <FormError id={errorId} message={error} />}
    </div>
  );
};
```

### 2. 도메인별 폼 컴포넌트

```typescript
// src/components/forms/CompanyForm.tsx
import React from 'react';
import { Card, CardBody, Button, Alert } from '@material-tailwind/react';
import { useCompanyForm } from '@/hooks/forms/useCompanyForm';
import { FormInput, FormSelect } from './common';
import { INDUSTRY_CODES } from '@/utils/constants';
import type { Company } from '@/types';

interface CompanyFormProps {
  /** 수정 모드일 때 기업 데이터 */
  company?: Company;
  /** 제출 성공 콜백 */
  onSuccess?: () => void;
  /** 취소 버튼 클릭 핸들러 */
  onCancel?: () => void;
}

/**
 * 기업 등록/수정 폼 컴포넌트
 * - 비즈니스 로직은 useCompanyForm 훅에서 처리
 * - UI 렌더링과 사용자 인터랙션만 담당
 */
export const CompanyForm: React.FC<CompanyFormProps> = ({
  company,
  onSuccess,
  onCancel,
}) => {
  const {
    formData,
    errors,
    touched,
    isSubmitting,
    isValid,
    isDirty,
    handleChange,
    handleBlur,
    handleSubmit,
    isEditMode,
  } = useCompanyForm({
    companyId: company?.company_id,
    initialData: company,
    onSuccess,
  });

  // 업종 옵션 변환
  const industryOptions = Object.entries(INDUSTRY_CODES).map(([code, name]) => ({
    value: code,
    label: name,
  }));

  return (
    <Card>
      <CardBody>
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* 회사명 */}
          <FormInput
            name="com_name"
            label="회사명"
            value={formData.com_name}
            onChange={(e) => handleChange('com_name', e.target.value)}
            onBlur={() => handleBlur('com_name')}
            error={touched.com_name ? errors.com_name : undefined}
            required
            maxLength={100}
          />

          {/* 사업자등록번호 */}
          <FormInput
            name="biz_num"
            label="사업자등록번호"
            value={formData.biz_num}
            onChange={(e) => handleChange('biz_num', e.target.value)}
            onBlur={() => handleBlur('biz_num')}
            error={touched.biz_num ? errors.biz_num : undefined}
            placeholder="000-00-00000"
            maxLength={12}
          />

          {/* 업종 */}
          <FormSelect
            name="biz_code"
            label="업종"
            value={formData.biz_code}
            onChange={(value) => handleChange('biz_code', value)}
            onBlur={() => handleBlur('biz_code')}
            options={industryOptions}
            error={touched.biz_code ? errors.biz_code : undefined}
            required
          />

          {/* 주소 */}
          <FormInput
            name="addr"
            label="주소"
            value={formData.addr}
            onChange={(e) => handleChange('addr', e.target.value)}
            onBlur={() => handleBlur('addr')}
            error={touched.addr ? errors.addr : undefined}
            maxLength={200}
          />

          {/* 개업일 */}
          <FormInput
            name="open_date"
            label="개업일"
            type="date"
            value={formData.open_date}
            onChange={(e) => handleChange('open_date', e.target.value)}
            onBlur={() => handleBlur('open_date')}
            error={touched.open_date ? errors.open_date : undefined}
          />

          {/* 버튼 영역 */}
          <div className="flex gap-2 pt-4">
            <Button
              type="submit"
              disabled={isSubmitting || !isValid || !isDirty}
              className="flex-1"
            >
              {isSubmitting ? '저장 중...' : isEditMode ? '수정' : '등록'}
            </Button>
            {onCancel && (
              <Button
                type="button"
                variant="outlined"
                onClick={onCancel}
                disabled={isSubmitting}
              >
                취소
              </Button>
            )}
          </div>
        </form>
      </CardBody>
    </Card>
  );
};
```

---

## 검증(Validation) 패턴

### 1. 검증 함수 유틸리티

```typescript
// src/utils/validation/validators.ts

/**
 * 빈 문자열 검증
 */
export const isRequired = (value: string): boolean => {
  return value.trim().length > 0;
};

/**
 * 이메일 형식 검증
 */
export const isEmail = (value: string): boolean => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(value);
};

/**
 * 사업자등록번호 검증 (000-00-00000)
 */
export const isBusinessNumber = (value: string): boolean => {
  const bizNumRegex = /^\d{3}-\d{2}-\d{5}$/;
  return bizNumRegex.test(value);
};

/**
 * 전화번호 검증 (010-0000-0000)
 */
export const isPhoneNumber = (value: string): boolean => {
  const phoneRegex = /^\d{2,3}-\d{3,4}-\d{4}$/;
  return phoneRegex.test(value);
};

/**
 * 날짜 형식 검증 (YYYY-MM-DD)
 */
export const isValidDate = (value: string): boolean => {
  const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
  if (!dateRegex.test(value)) return false;

  const date = new Date(value);
  return !isNaN(date.getTime());
};

/**
 * 최소 길이 검증
 */
export const minLength = (value: string, min: number): boolean => {
  return value.length >= min;
};

/**
 * 최대 길이 검증
 */
export const maxLength = (value: string, max: number): boolean => {
  return value.length <= max;
};

/**
 * 숫자 범위 검증
 */
export const inRange = (value: number, min: number, max: number): boolean => {
  return value >= min && value <= max;
};
```

### 2. 도메인별 검증 함수

```typescript
// src/utils/validation/validators.ts (계속)
import type { CompanyFormData, ProfileFormData } from '@/types/forms';

/**
 * 기업 폼 검증
 */
export const validateCompanyForm = (
  values: CompanyFormData
): Partial<Record<keyof CompanyFormData, string>> => {
  const errors: Partial<Record<keyof CompanyFormData, string>> = {};

  // 회사명 검증
  if (!isRequired(values.com_name)) {
    errors.com_name = '회사명을 입력해주세요.';
  } else if (!maxLength(values.com_name, 100)) {
    errors.com_name = '회사명은 100자 이내로 입력해주세요.';
  }

  // 사업자등록번호 검증 (선택 필드지만 입력 시 형식 확인)
  if (values.biz_num && !isBusinessNumber(values.biz_num)) {
    errors.biz_num = '사업자등록번호 형식이 올바르지 않습니다. (예: 123-45-67890)';
  }

  // 업종 검증
  if (!isRequired(values.biz_code)) {
    errors.biz_code = '업종을 선택해주세요.';
  }

  // 개업일 검증 (선택 필드지만 입력 시 형식 확인)
  if (values.open_date && !isValidDate(values.open_date)) {
    errors.open_date = '올바른 날짜 형식이 아닙니다.';
  }

  return errors;
};

/**
 * 프로필 폼 검증
 */
export const validateProfileForm = (
  values: ProfileFormData
): Partial<Record<keyof ProfileFormData, string>> => {
  const errors: Partial<Record<keyof ProfileFormData, string>> = {};

  // 사용자 이름 검증
  if (!isRequired(values.username)) {
    errors.username = '이름을 입력해주세요.';
  } else if (!minLength(values.username, 2)) {
    errors.username = '이름은 최소 2자 이상이어야 합니다.';
  } else if (!maxLength(values.username, 50)) {
    errors.username = '이름은 50자 이내로 입력해주세요.';
  }

  // 사용자 유형 검증
  if (!['U001', 'U002', 'U003'].includes(values.type_code)) {
    errors.type_code = '올바른 사용자 유형을 선택해주세요.';
  }

  // 생년월일 검증 (선택 필드)
  if (values.birth && !isValidDate(values.birth)) {
    errors.birth = '올바른 날짜 형식이 아닙니다.';
  }

  return errors;
};
```

### 3. 비동기 검증 (서버 검증)

```typescript
// src/utils/validation/asyncValidators.ts
import api from '@/lib/api';

/**
 * 사업자등록번호 중복 검증 (비동기)
 */
export const validateBusinessNumberUnique = async (
  bizNum: string,
  excludeCompanyId?: number
): Promise<string | undefined> => {
  if (!bizNum) return undefined;

  try {
    const response = await api.get('/companies/check-biz-num', {
      params: { biz_num: bizNum, exclude_id: excludeCompanyId },
    });

    if (response.data.exists) {
      return '이미 등록된 사업자등록번호입니다.';
    }
    return undefined;
  } catch (error) {
    return '사업자등록번호 확인에 실패했습니다.';
  }
};

/**
 * 이메일 중복 검증 (비동기)
 */
export const validateEmailUnique = async (
  email: string
): Promise<string | undefined> => {
  if (!email) return undefined;

  try {
    const response = await api.get('/users/check-email', {
      params: { email },
    });

    if (response.data.exists) {
      return '이미 사용 중인 이메일입니다.';
    }
    return undefined;
  } catch (error) {
    return '이메일 확인에 실패했습니다.';
  }
};
```

---

## 에러 처리 및 표시

### 1. 에러 메시지 상수

```typescript
// src/utils/validation/constants.ts

/**
 * 공통 에러 메시지
 */
export const ERROR_MESSAGES = {
  REQUIRED: '필수 입력 항목입니다.',
  INVALID_FORMAT: '형식이 올바르지 않습니다.',
  INVALID_EMAIL: '올바른 이메일 주소를 입력해주세요.',
  INVALID_PHONE: '올바른 전화번호 형식이 아닙니다. (예: 010-1234-5678)',
  INVALID_DATE: '올바른 날짜 형식이 아닙니다.',
  MIN_LENGTH: (min: number) => `최소 ${min}자 이상 입력해주세요.`,
  MAX_LENGTH: (max: number) => `최대 ${max}자 이내로 입력해주세요.`,
  MIN_VALUE: (min: number) => `최소값은 ${min}입니다.`,
  MAX_VALUE: (max: number) => `최대값은 ${max}입니다.`,
  SERVER_ERROR: '서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
  NETWORK_ERROR: '네트워크 연결을 확인해주세요.',
} as const;

/**
 * 필드별 에러 메시지
 */
export const FIELD_ERROR_MESSAGES = {
  com_name: {
    required: '회사명을 입력해주세요.',
    maxLength: '회사명은 100자 이내로 입력해주세요.',
  },
  biz_num: {
    invalid: '사업자등록번호 형식이 올바르지 않습니다. (예: 123-45-67890)',
    duplicate: '이미 등록된 사업자등록번호입니다.',
  },
  username: {
    required: '이름을 입력해주세요.',
    minLength: '이름은 최소 2자 이상이어야 합니다.',
    maxLength: '이름은 50자 이내로 입력해주세요.',
  },
} as const;
```

### 2. 에러 처리 유틸리티

```typescript
// src/utils/error/errorHandler.ts
import { AxiosError } from 'axios';

/**
 * API 에러를 사용자 친화적 메시지로 변환
 */
export const handleApiError = (error: unknown): string => {
  if (error instanceof AxiosError) {
    // 백엔드에서 반환한 상세 에러 메시지
    if (error.response?.data?.detail) {
      return error.response.data.detail;
    }

    // HTTP 상태 코드별 처리
    switch (error.response?.status) {
      case 400:
        return '입력 정보를 확인해주세요.';
      case 401:
        return '로그인이 필요합니다.';
      case 403:
        return '접근 권한이 없습니다.';
      case 404:
        return '요청한 정보를 찾을 수 없습니다.';
      case 409:
        return '이미 존재하는 정보입니다.';
      case 500:
        return '서버 오류가 발생했습니다.';
      default:
        return '오류가 발생했습니다. 잠시 후 다시 시도해주세요.';
    }
  }

  if (error instanceof Error) {
    return error.message;
  }

  return '알 수 없는 오류가 발생했습니다.';
};

/**
 * 필드별 서버 에러를 폼 에러로 매핑
 */
export const mapServerErrorsToFormErrors = <T extends Record<string, any>>(
  serverErrors: Record<string, string[]>
): Partial<Record<keyof T, string>> => {
  const formErrors: Partial<Record<keyof T, string>> = {};

  Object.entries(serverErrors).forEach(([field, messages]) => {
    if (Array.isArray(messages) && messages.length > 0) {
      formErrors[field as keyof T] = messages[0];
    }
  });

  return formErrors;
};
```

### 3. 에러 표시 컴포넌트

```typescript
// src/components/forms/common/FormErrorSummary.tsx
import React from 'react';
import { Alert } from '@material-tailwind/react';
import { XCircleIcon } from '@heroicons/react/24/outline';

interface FormErrorSummaryProps {
  /** 에러 메시지 배열 */
  errors: string[];
  /** 닫기 핸들러 */
  onClose?: () => void;
  /** 추가 CSS 클래스 */
  className?: string;
}

/**
 * 폼 전체 에러 요약 컴포넌트
 * - 여러 필드 에러를 한 번에 표시
 */
export const FormErrorSummary: React.FC<FormErrorSummaryProps> = ({
  errors,
  onClose,
  className = '',
}) => {
  if (errors.length === 0) return null;

  return (
    <Alert
      color="red"
      icon={<XCircleIcon className="h-5 w-5" />}
      className={className}
      onClose={onClose}
    >
      <div>
        <p className="font-medium mb-2">다음 항목을 확인해주세요:</p>
        <ul className="list-disc list-inside space-y-1">
          {errors.map((error, index) => (
            <li key={index} className="text-sm">
              {error}
            </li>
          ))}
        </ul>
      </div>
    </Alert>
  );
};
```

---

## 상태 관리

### 1. Zustand를 활용한 폼 상태 관리 (복잡한 폼)

```typescript
// src/stores/companyFormStore.ts
import { create } from 'zustand';
import type { CompanyFormData, CompanyFormState } from '@/types/forms/company.types';

interface CompanyFormStore extends CompanyFormState {
  setFormData: (data: Partial<CompanyFormData>) => void;
  setFieldValue: <K extends keyof CompanyFormData>(name: K, value: CompanyFormData[K]) => void;
  setFieldError: (name: keyof CompanyFormData, error: string) => void;
  clearErrors: () => void;
  resetForm: () => void;
}

const initialFormData: CompanyFormData = {
  com_name: '',
  biz_num: '',
  addr: '',
  open_date: '',
  biz_code: 'B001',
};

/**
 * 기업 폼 전역 상태 스토어
 * - 복잡한 다단계 폼이나 여러 컴포넌트에서 공유해야 하는 경우 사용
 */
export const useCompanyFormStore = create<CompanyFormStore>((set) => ({
  data: initialFormData,
  errors: {},
  touched: {},
  isSubmitting: false,
  isValid: false,
  isDirty: false,

  setFormData: (data) =>
    set((state) => ({
      data: { ...state.data, ...data },
      isDirty: true,
    })),

  setFieldValue: (name, value) =>
    set((state) => ({
      data: { ...state.data, [name]: value },
      isDirty: true,
    })),

  setFieldError: (name, error) =>
    set((state) => ({
      errors: { ...state.errors, [name]: error },
    })),

  clearErrors: () => set({ errors: {} }),

  resetForm: () =>
    set({
      data: initialFormData,
      errors: {},
      touched: {},
      isSubmitting: false,
      isValid: false,
      isDirty: false,
    }),
}));
```

### 2. 로컬 상태 vs 전역 상태 선택 가이드

```typescript
/**
 * 로컬 상태 (useState + 커스텀 훅) 사용 시나리오:
 * ✓ 단일 페이지/컴포넌트 내에서만 사용되는 폼
 * ✓ 단순한 폼 (5개 이하 필드)
 * ✓ 다른 컴포넌트와 상태 공유 불필요
 *
 * 예: 프로필 수정, 간단한 설정 폼
 */

/**
 * 전역 상태 (Zustand) 사용 시나리오:
 * ✓ 다단계(Multi-step) 폼
 * ✓ 여러 컴포넌트에서 동일한 폼 데이터 접근 필요
 * ✓ 폼 데이터를 페이지 이동 간에 유지해야 함
 * ✓ 복잡한 폼 (10개 이상 필드, 동적 필드)
 *
 * 예: 기업 등록 위저드, 복잡한 신청서
 */
```

---

## 재사용 가능한 폼 컴포넌트

### 1. 추가 Atomic 컴포넌트

```typescript
// src/components/forms/common/FormTextarea.tsx
import React from 'react';
import { Textarea } from '@material-tailwind/react';
import { FormLabel } from './FormLabel';
import { FormError } from './FormError';

interface FormTextareaProps {
  name: string;
  label: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  onBlur?: (e: React.FocusEvent<HTMLTextAreaElement>) => void;
  error?: string;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  rows?: number;
  maxLength?: number;
  className?: string;
}

export const FormTextarea: React.FC<FormTextareaProps> = ({
  name,
  label,
  value,
  onChange,
  onBlur,
  error,
  placeholder,
  required = false,
  disabled = false,
  rows = 4,
  maxLength,
  className,
}) => {
  const textareaId = `form-textarea-${name}`;
  const errorId = `form-error-${name}`;
  const hasError = Boolean(error);

  return (
    <div className={className}>
      <FormLabel htmlFor={textareaId} required={required}>
        {label}
      </FormLabel>

      <Textarea
        id={textareaId}
        name={name}
        value={value}
        onChange={onChange}
        onBlur={onBlur}
        placeholder={placeholder}
        disabled={disabled}
        rows={rows}
        maxLength={maxLength}
        className={`!border-gray-300 ${hasError ? '!border-red-500' : ''}`}
        labelProps={{ className: 'hidden' }}
        aria-invalid={hasError}
        aria-describedby={hasError ? errorId : undefined}
        aria-required={required}
      />

      {maxLength && (
        <div className="text-right mt-1">
          <Typography variant="small" color="gray">
            {value.length} / {maxLength}
          </Typography>
        </div>
      )}

      {hasError && <FormError id={errorId} message={error} />}
    </div>
  );
};
```

```typescript
// src/components/forms/common/FormCheckbox.tsx
import React from 'react';
import { Checkbox, Typography } from '@material-tailwind/react';
import { FormError } from './FormError';

interface FormCheckboxProps {
  name: string;
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  error?: string;
  disabled?: boolean;
  className?: string;
}

export const FormCheckbox: React.FC<FormCheckboxProps> = ({
  name,
  label,
  checked,
  onChange,
  error,
  disabled = false,
  className,
}) => {
  const checkboxId = `form-checkbox-${name}`;
  const errorId = `form-error-${name}`;
  const hasError = Boolean(error);

  return (
    <div className={className}>
      <Checkbox
        id={checkboxId}
        name={name}
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
        label={
          <Typography variant="small" color="gray" className="font-normal">
            {label}
          </Typography>
        }
        aria-invalid={hasError}
        aria-describedby={hasError ? errorId : undefined}
      />

      {hasError && <FormError id={errorId} message={error} />}
    </div>
  );
};
```

### 2. 컴포지트 컴포넌트 (조합형)

```typescript
// src/components/forms/common/FormField.tsx
import React from 'react';
import { FormInput } from './FormInput';
import { FormSelect } from './FormSelect';
import { FormTextarea } from './FormTextarea';
import { FormCheckbox } from './FormCheckbox';

type FormFieldType = 'text' | 'email' | 'password' | 'number' | 'date' | 'select' | 'textarea' | 'checkbox';

interface BaseFormFieldProps {
  name: string;
  label: string;
  type: FormFieldType;
  value: any;
  onChange: (value: any) => void;
  onBlur?: () => void;
  error?: string;
  required?: boolean;
  disabled?: boolean;
  className?: string;
}

interface TextFormFieldProps extends BaseFormFieldProps {
  type: 'text' | 'email' | 'password' | 'number' | 'date';
  placeholder?: string;
  maxLength?: number;
}

interface SelectFormFieldProps extends BaseFormFieldProps {
  type: 'select';
  options: Array<{ value: string; label: string }>;
  placeholder?: string;
}

interface TextareaFormFieldProps extends BaseFormFieldProps {
  type: 'textarea';
  placeholder?: string;
  rows?: number;
  maxLength?: number;
}

interface CheckboxFormFieldProps extends BaseFormFieldProps {
  type: 'checkbox';
  value: boolean;
}

type FormFieldProps =
  | TextFormFieldProps
  | SelectFormFieldProps
  | TextareaFormFieldProps
  | CheckboxFormFieldProps;

/**
 * 통합 폼 필드 컴포넌트
 * - 타입에 따라 적절한 입력 컴포넌트 렌더링
 */
export const FormField: React.FC<FormFieldProps> = (props) => {
  const { type, name, label, value, onChange, onBlur, error, required, disabled, className } = props;

  switch (type) {
    case 'text':
    case 'email':
    case 'password':
    case 'number':
    case 'date':
      return (
        <FormInput
          name={name}
          label={label}
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur}
          error={error}
          placeholder={(props as TextFormFieldProps).placeholder}
          maxLength={(props as TextFormFieldProps).maxLength}
          required={required}
          disabled={disabled}
          className={className}
        />
      );

    case 'select':
      return (
        <FormSelect
          name={name}
          label={label}
          value={value}
          onChange={onChange}
          onBlur={onBlur}
          options={(props as SelectFormFieldProps).options}
          error={error}
          placeholder={(props as SelectFormFieldProps).placeholder}
          required={required}
          disabled={disabled}
          className={className}
        />
      );

    case 'textarea':
      return (
        <FormTextarea
          name={name}
          label={label}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur}
          error={error}
          placeholder={(props as TextareaFormFieldProps).placeholder}
          rows={(props as TextareaFormFieldProps).rows}
          maxLength={(props as TextareaFormFieldProps).maxLength}
          required={required}
          disabled={disabled}
          className={className}
        />
      );

    case 'checkbox':
      return (
        <FormCheckbox
          name={name}
          label={label}
          checked={value}
          onChange={onChange}
          error={error}
          disabled={disabled}
          className={className}
        />
      );

    default:
      return null;
  }
};
```

---

## 접근성

### 1. 필수 접근성 체크리스트

```typescript
/**
 * 폼 접근성 체크리스트
 *
 * ✓ 모든 입력 필드에 <label> 또는 aria-label 제공
 * ✓ 필수 필드에 aria-required="true" 속성 추가
 * ✓ 에러가 있는 필드에 aria-invalid="true" 속성 추가
 * ✓ 에러 메시지와 필드를 aria-describedby로 연결
 * ✓ 에러 메시지에 role="alert" 및 aria-live="polite" 적용
 * ✓ 키보드만으로 모든 폼 기능 접근 가능 (Tab, Enter, Space)
 * ✓ 포커스 스타일 명확하게 표시
 * ✓ 폼 제출 시 에러가 있으면 첫 번째 에러 필드로 포커스 이동
 * ✓ 로딩 중일 때 버튼 비활성화 및 aria-busy 속성 적용
 */
```

### 2. 접근성 개선 유틸리티

```typescript
// src/utils/accessibility/focusManagement.ts

/**
 * 첫 번째 에러 필드로 포커스 이동
 */
export const focusFirstError = (errors: Record<string, string>): void => {
  const firstErrorField = Object.keys(errors)[0];
  if (!firstErrorField) return;

  const element = document.getElementById(`form-input-${firstErrorField}`);
  if (element) {
    element.focus();
    // 스크린 리더를 위한 에러 알림
    element.setAttribute('aria-invalid', 'true');
  }
};

/**
 * 폼 제출 시 스크린 리더에 결과 알림
 */
export const announceFormResult = (message: string, type: 'success' | 'error'): void => {
  const liveRegion = document.getElementById('form-live-region');
  if (liveRegion) {
    liveRegion.textContent = message;
    liveRegion.setAttribute('aria-live', type === 'error' ? 'assertive' : 'polite');
  }
};
```

### 3. 접근성 컴포넌트

```typescript
// src/components/forms/common/FormLiveRegion.tsx
import React from 'react';

/**
 * 스크린 리더용 라이브 리전
 * - 폼 제출 결과를 스크린 리더에 알림
 */
export const FormLiveRegion: React.FC = () => {
  return (
    <div
      id="form-live-region"
      role="status"
      aria-live="polite"
      aria-atomic="true"
      className="sr-only"
    />
  );
};
```

---

## 실전 예제

### 예제 1: 기업 등록 폼 (전체 구현)

#### 1-1. 타입 정의
```typescript
// src/types/forms/company.types.ts
import type { FormState } from './common.types';

export interface CompanyFormData {
  com_name: string;
  biz_num: string;
  addr: string;
  open_date: string;
  biz_code: string;
  file_path?: string;
}

export type CompanyFormState = FormState<CompanyFormData>;
```

#### 1-2. 검증 함수
```typescript
// src/utils/validation/companyValidators.ts
import type { CompanyFormData } from '@/types/forms/company.types';
import { isRequired, isBusinessNumber, isValidDate, maxLength } from './validators';
import { FIELD_ERROR_MESSAGES } from './constants';

export const validateCompanyForm = (
  values: CompanyFormData
): Partial<Record<keyof CompanyFormData, string>> => {
  const errors: Partial<Record<keyof CompanyFormData, string>> = {};

  if (!isRequired(values.com_name)) {
    errors.com_name = FIELD_ERROR_MESSAGES.com_name.required;
  } else if (!maxLength(values.com_name, 100)) {
    errors.com_name = FIELD_ERROR_MESSAGES.com_name.maxLength;
  }

  if (values.biz_num && !isBusinessNumber(values.biz_num)) {
    errors.biz_num = FIELD_ERROR_MESSAGES.biz_num.invalid;
  }

  if (!isRequired(values.biz_code)) {
    errors.biz_code = '업종을 선택해주세요.';
  }

  if (values.open_date && !isValidDate(values.open_date)) {
    errors.open_date = '올바른 날짜 형식이 아닙니다.';
  }

  return errors;
};
```

#### 1-3. 커스텀 훅
```typescript
// src/hooks/forms/useCompanyForm.ts
import { useCallback } from 'react';
import { useForm } from './useForm';
import { validateCompanyForm } from '@/utils/validation/companyValidators';
import { handleApiError } from '@/utils/error/errorHandler';
import api from '@/lib/api';
import type { CompanyFormData } from '@/types/forms/company.types';
import type { Company } from '@/types';

interface UseCompanyFormOptions {
  companyId?: number;
  initialData?: Partial<CompanyFormData>;
  onSuccess?: (company: Company) => void;
  onError?: (error: string) => void;
}

export function useCompanyForm(options: UseCompanyFormOptions = {}) {
  const { companyId, initialData, onSuccess, onError } = options;

  const isEditMode = Boolean(companyId);

  const handleSubmit = useCallback(
    async (values: CompanyFormData) => {
      const submitData = {
        ...values,
        open_date: values.open_date ? new Date(values.open_date).toISOString() : null,
      };

      try {
        const response = isEditMode
          ? await api.put(`/companies/${companyId}`, submitData)
          : await api.post('/companies', submitData);

        onSuccess?.(response.data);
      } catch (error) {
        const errorMessage = handleApiError(error);
        onError?.(errorMessage);
        throw error;
      }
    },
    [companyId, isEditMode, onSuccess, onError]
  );

  const formHook = useForm<CompanyFormData>({
    initialValues: {
      com_name: initialData?.com_name || '',
      biz_num: initialData?.biz_num || '',
      addr: initialData?.addr || '',
      open_date: initialData?.open_date || '',
      biz_code: initialData?.biz_code || 'B001',
      file_path: initialData?.file_path || '',
    },
    validate: validateCompanyForm,
    onSubmit: handleSubmit,
  });

  return {
    ...formHook,
    isEditMode,
  };
}
```

#### 1-4. 폼 컴포넌트
```typescript
// src/components/forms/CompanyForm.tsx
import React, { useState } from 'react';
import { Card, CardBody, Button, Alert } from '@material-tailwind/react';
import { useCompanyForm } from '@/hooks/forms/useCompanyForm';
import { FormInput, FormSelect, FormLiveRegion } from './common';
import { INDUSTRY_CODES } from '@/utils/constants';
import type { Company } from '@/types';

interface CompanyFormProps {
  company?: Company;
  onSuccess?: () => void;
  onCancel?: () => void;
}

export const CompanyForm: React.FC<CompanyFormProps> = ({
  company,
  onSuccess: onSuccessProp,
  onCancel,
}) => {
  const [successMessage, setSuccessMessage] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string>('');

  const {
    formData,
    errors,
    touched,
    isSubmitting,
    isValid,
    isDirty,
    handleChange,
    handleBlur,
    handleSubmit,
    isEditMode,
  } = useCompanyForm({
    companyId: company?.company_id,
    initialData: company,
    onSuccess: () => {
      setSuccessMessage(
        isEditMode ? '기업 정보가 수정되었습니다.' : '기업이 등록되었습니다.'
      );
      setErrorMessage('');
      onSuccessProp?.();
    },
    onError: (error) => {
      setErrorMessage(error);
      setSuccessMessage('');
    },
  });

  const industryOptions = Object.entries(INDUSTRY_CODES).map(([code, name]) => ({
    value: code,
    label: name,
  }));

  return (
    <>
      <FormLiveRegion />

      <Card>
        <CardBody>
          {successMessage && (
            <Alert color="green" className="mb-4" onClose={() => setSuccessMessage('')}>
              {successMessage}
            </Alert>
          )}

          {errorMessage && (
            <Alert color="red" className="mb-4" onClose={() => setErrorMessage('')}>
              {errorMessage}
            </Alert>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <FormInput
              name="com_name"
              label="회사명"
              value={formData.com_name}
              onChange={(e) => handleChange('com_name', e.target.value)}
              onBlur={() => handleBlur('com_name')}
              error={touched.com_name ? errors.com_name : undefined}
              required
              maxLength={100}
              autoComplete="organization"
            />

            <FormInput
              name="biz_num"
              label="사업자등록번호"
              value={formData.biz_num}
              onChange={(e) => handleChange('biz_num', e.target.value)}
              onBlur={() => handleBlur('biz_num')}
              error={touched.biz_num ? errors.biz_num : undefined}
              placeholder="123-45-67890"
              maxLength={12}
            />

            <FormSelect
              name="biz_code"
              label="업종"
              value={formData.biz_code}
              onChange={(value) => handleChange('biz_code', value)}
              onBlur={() => handleBlur('biz_code')}
              options={industryOptions}
              error={touched.biz_code ? errors.biz_code : undefined}
              required
            />

            <FormInput
              name="addr"
              label="주소"
              value={formData.addr}
              onChange={(e) => handleChange('addr', e.target.value)}
              onBlur={() => handleBlur('addr')}
              error={touched.addr ? errors.addr : undefined}
              maxLength={200}
              autoComplete="street-address"
            />

            <FormInput
              name="open_date"
              label="개업일"
              type="date"
              value={formData.open_date}
              onChange={(e) => handleChange('open_date', e.target.value)}
              onBlur={() => handleBlur('open_date')}
              error={touched.open_date ? errors.open_date : undefined}
            />

            <div className="flex gap-2 pt-4">
              <Button
                type="submit"
                disabled={isSubmitting || !isValid || !isDirty}
                className="flex-1"
                aria-busy={isSubmitting}
              >
                {isSubmitting ? '저장 중...' : isEditMode ? '수정' : '등록'}
              </Button>
              {onCancel && (
                <Button
                  type="button"
                  variant="outlined"
                  onClick={onCancel}
                  disabled={isSubmitting}
                >
                  취소
                </Button>
              )}
            </div>
          </form>
        </CardBody>
      </Card>
    </>
  );
};
```

### 예제 2: 프로필 수정 폼 (간단한 폼)

```typescript
// src/hooks/forms/useProfileForm.ts
import { useCallback } from 'react';
import { useForm } from './useForm';
import { validateProfileForm } from '@/utils/validation/profileValidators';
import { useAuthStore } from '@/stores/authStore';
import api from '@/lib/api';
import type { ProfileFormData } from '@/types/forms/profile.types';

export function useProfileForm(onSuccess?: () => void) {
  const { user, updateUser } = useAuthStore();

  const handleSubmit = useCallback(
    async (values: ProfileFormData) => {
      // 이름 업데이트
      if (values.username !== user?.username) {
        await api.put('/users/me', { username: values.username });
      }

      // 타입 업데이트
      if (values.type_code !== user?.type_code) {
        await api.put('/users/me/type', { type_code: values.type_code });
      }

      // 로컬 상태 업데이트
      updateUser({
        username: values.username,
        type_code: values.type_code,
      });
    },
    [user, updateUser]
  );

  return useForm<ProfileFormData>({
    initialValues: {
      username: user?.username || '',
      type_code: user?.type_code || 'U002',
      birth: user?.birth || '',
    },
    validate: validateProfileForm,
    onSubmit: handleSubmit,
    onSuccess,
  });
}
```

---

## 마이그레이션 가이드

### 기존 폼을 새 아키텍처로 전환하기

#### Before (기존 패턴)
```typescript
// 비즈니스 로직과 UI가 혼재된 컴포넌트
const CompanyPage = () => {
  const [formData, setFormData] = useState({ ... });
  const [errors, setErrors] = useState({});

  const handleSubmit = async () => {
    // 검증 로직
    if (!formData.com_name) {
      setErrors({ com_name: '회사명을 입력하세요' });
      return;
    }

    // API 호출
    try {
      await api.post('/companies', formData);
    } catch (err) {
      // 에러 처리
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <Input
        value={formData.com_name}
        onChange={(e) => setFormData({ ...formData, com_name: e.target.value })}
      />
      {/* ... */}
    </form>
  );
};
```

#### After (새 아키텍처)
```typescript
// 1. 타입 정의 (src/types/forms/company.types.ts)
export interface CompanyFormData {
  com_name: string;
  // ...
}

// 2. 검증 함수 (src/utils/validation/companyValidators.ts)
export const validateCompanyForm = (values: CompanyFormData) => {
  // ...
};

// 3. 커스텀 훅 (src/hooks/forms/useCompanyForm.ts)
export function useCompanyForm(options) {
  // ...
}

// 4. 컴포넌트 (src/components/forms/CompanyForm.tsx)
export const CompanyForm = ({ company, onSuccess }) => {
  const {
    formData,
    errors,
    touched,
    handleChange,
    handleBlur,
    handleSubmit,
  } = useCompanyForm({ initialData: company, onSuccess });

  return (
    <form onSubmit={handleSubmit}>
      <FormInput
        name="com_name"
        label="회사명"
        value={formData.com_name}
        onChange={(e) => handleChange('com_name', e.target.value)}
        onBlur={() => handleBlur('com_name')}
        error={touched.com_name ? errors.com_name : undefined}
        required
      />
    </form>
  );
};
```

---

## 코드 리뷰 체크리스트

폼 코드를 작성하거나 리뷰할 때 다음 항목을 확인하세요:

### 아키텍처
- [ ] 타입 정의가 `src/types/forms/`에 분리되어 있는가?
- [ ] 비즈니스 로직이 커스텀 훅으로 분리되어 있는가?
- [ ] UI 컴포넌트가 프레젠테이션에만 집중하는가?

### TypeScript
- [ ] 모든 폼 데이터에 명시적 인터페이스가 정의되어 있는가?
- [ ] `any` 타입을 사용하지 않았는가? (불가피한 경우 주석 첨부)
- [ ] 제네릭을 적절히 활용하였는가?

### 검증
- [ ] 클라이언트 측 검증이 구현되어 있는가?
- [ ] 에러 메시지가 사용자 친화적인가?
- [ ] 필수 필드가 명확히 표시되는가?

### 접근성
- [ ] 모든 입력 필드에 label 또는 aria-label이 있는가?
- [ ] 에러 메시지가 스크린 리더로 읽히는가?
- [ ] 키보드만으로 폼을 작성할 수 있는가?

### 재사용성
- [ ] Atomic 폼 컴포넌트를 활용하였는가?
- [ ] 중복 코드가 없는가?
- [ ] 설정 가능한 props를 제공하는가?

### 성능
- [ ] 불필요한 리렌더링이 발생하지 않는가?
- [ ] useCallback, useMemo를 적절히 사용하였는가?

---

## 참고 자료

### 내부 문서
- `frontend/CLAUDE.md`: Frontend 전체 개발 가이드
- `frontend/src/types/index.ts`: 공통 타입 정의
- `frontend/src/lib/api.ts`: API 클라이언트 설정

### 외부 라이브러리 문서
- [Material Tailwind Components](https://www.material-tailwind.com/docs/react/input)
- [React Hook Form](https://react-hook-form.com/) (참고용, 현재 미사용)
- [Zod](https://zod.dev/) (향후 스키마 검증 도입 시 고려)

### 접근성 가이드
- [WAI-ARIA Authoring Practices - Forms](https://www.w3.org/WAI/ARIA/apg/patterns/)
- [WebAIM - Creating Accessible Forms](https://webaim.org/techniques/forms/)

---

## 버전 이력
- **v1.0** (2026-01-29): 초기 문서 작성

---

**이 문서는 프로젝트의 폼 개발 표준이며, 모든 팀원이 준수해야 합니다.**
**새로운 패턴이나 개선 사항이 발견되면 이 문서를 업데이트하세요.**
