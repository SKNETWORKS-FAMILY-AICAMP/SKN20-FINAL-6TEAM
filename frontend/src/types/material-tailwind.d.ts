/**
 * Material-Tailwind v2.1.8 + @types/react 18.2.x 호환성 타입 보강
 *
 * Material-Tailwind 컴포넌트가 placeholder, crossOrigin,
 * onPointerEnterCapture, onPointerLeaveCapture를 필수 props로
 * 요구하는 타입 버그를 해결합니다.
 */

import type React from 'react';

type Omitted =
  | 'placeholder'
  | 'onPointerEnterCapture'
  | 'onPointerLeaveCapture';

type InputOmitted = Omitted | 'crossOrigin';

declare module '@material-tailwind/react' {
  // Layout
  export interface CardProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }
  export interface CardHeaderProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }
  export interface CardBodyProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }
  export interface CardFooterProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }

  // Typography
  export interface TypographyProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }

  // Buttons
  export interface ButtonProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }
  export interface IconButtonProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }
  export interface ButtonGroupProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }

  // Dialog
  export interface DialogProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }
  export interface DialogHeaderProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }
  export interface DialogBodyProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }
  export interface DialogFooterProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }

  // Form
  export interface InputProps {
    placeholder?: string;
    crossOrigin?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }
  export interface TextareaProps {
    placeholder?: string;
    crossOrigin?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }
  export interface SelectProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }

  // Chip, Spinner, Alert
  export interface ChipProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }
  export interface SpinnerProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }
  export interface AlertProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }

  // List
  export interface ListProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }
  export interface ListItemProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }
  export interface ListItemPrefixProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }
  export interface ListItemSuffixProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }

  // Accordion
  export interface AccordionProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }
  export interface AccordionHeaderProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }
  export interface AccordionBodyProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }

  // Tooltip
  export interface TooltipProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }

  // Tabs
  export interface TabsProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }
  export interface TabsHeaderProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }
  export interface TabsBodyProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }
  export interface TabProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }
  export interface TabPanelProps {
    placeholder?: string;
    onPointerEnterCapture?: React.PointerEventHandler;
    onPointerLeaveCapture?: React.PointerEventHandler;
  }
}
