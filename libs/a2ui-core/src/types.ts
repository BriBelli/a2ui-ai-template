/**
 * A2UI Core Types
 * 
 * A2UI is a declarative JSON format for representing updateable agent-generated UIs.
 * These types define the core data structures used across all A2UI implementations.
 * 
 * @see https://github.com/google/A2UI
 */

/**
 * Base component interface - all A2UI components extend this
 *
 * Supports two child formats:
 * - **Flat / referenced**: `children` is `string[]` of component IDs
 *   (used with `A2UIResponse.root` for the original A2UI spec)
 * - **Nested / inline**: `children` is `A2UIComponent[]` of inline objects
 *   (natural format for LLM-generated responses)
 */
export interface A2UIComponent {
  /** Unique identifier for the component */
  id: string;
  /** Component type from the registry (e.g., 'card', 'button', 'text-field') */
  type: string;
  /** Component properties specific to the type */
  props?: Record<string, unknown>;
  /**
   * Child components — either string IDs (flat/referenced mode)
   * or inline A2UIComponent objects (nested mode, typical of LLM output).
   */
  children?: string[] | A2UIComponent[];
  /** Event handlers mapped to action names */
  events?: Record<string, A2UIAction>;
  /** Data bindings for reactive updates */
  bindings?: Record<string, string>;
  /** Conditional rendering expression */
  when?: string;
  /** Accessibility attributes */
  a11y?: A2UIAccessibility;
}

/**
 * Action triggered by component events
 */
export interface A2UIAction {
  /** Type of action to perform */
  type: 'submit' | 'navigate' | 'update' | 'custom';
  /** Target for the action (URL, component ID, etc.) */
  target?: string;
  /** Payload to send with the action */
  payload?: Record<string, unknown>;
  /** Custom action name for 'custom' type */
  name?: string;
}

/**
 * Accessibility attributes for components
 */
export interface A2UIAccessibility {
  label?: string;
  description?: string;
  role?: string;
  live?: 'off' | 'polite' | 'assertive';
}

/**
 * The complete A2UI response from an agent.
 *
 * Supports two modes:
 * - **Flat**: `components` is a flat list, `root` points to the entry component,
 *   and children are string ID references. (Original A2UI spec.)
 * - **Nested**: `components` contains top-level components with inline children.
 *   `root` is optional in this mode. (Natural LLM output format.)
 */
export interface A2UIResponse {
  /** Version of the A2UI specification */
  version: string;
  /** List of components (flat with ID references, or nested with inline children) */
  components: A2UIComponent[];
  /** Root component ID to start rendering from (required in flat mode, optional in nested) */
  root?: string;
  /** Initial data model for bindings */
  data?: Record<string, unknown>;
  /** Metadata about the response */
  meta?: A2UIMetadata;
}

/**
 * Metadata about an A2UI response
 */
export interface A2UIMetadata {
  /** Title for the UI */
  title?: string;
  /** Description of the UI */
  description?: string;
  /** Agent that generated the response */
  agent?: string;
  /** Timestamp of generation */
  timestamp?: string;
  /** Custom metadata */
  [key: string]: unknown;
}

/**
 * Update payload for incremental UI changes
 */
export interface A2UIUpdate {
  /** Type of update operation */
  operation: 'add' | 'remove' | 'update' | 'replace';
  /** Target component ID */
  targetId: string;
  /** Updated component data (for add/update/replace) */
  component?: Partial<A2UIComponent>;
  /** Updated data model values */
  data?: Record<string, unknown>;
}

/**
 * Event emitted by components
 */
export interface A2UIEvent {
  /** Type of event */
  type: string;
  /** Component that emitted the event */
  componentId: string;
  /** Event payload */
  payload?: Record<string, unknown>;
  /** Timestamp of the event */
  timestamp: number;
}

/**
 * Result of an action execution
 */
export interface A2UIActionResult {
  /** Whether the action succeeded */
  success: boolean;
  /** Error message if failed */
  error?: string;
  /** Response data from the action */
  data?: Record<string, unknown>;
  /** Follow-up updates to apply */
  updates?: A2UIUpdate[];
}

// ============================================
// Built-in Component Types
// ============================================

export interface CardProps {
  title?: string;
  subtitle?: string;
  elevation?: number;
  outlined?: boolean;
}

export interface ButtonProps {
  label: string;
  variant?: 'filled' | 'outlined' | 'text' | 'elevated';
  disabled?: boolean;
  loading?: boolean;
  icon?: string;
}

export interface TextFieldProps {
  label?: string;
  placeholder?: string;
  value?: string;
  type?: 'text' | 'password' | 'email' | 'number' | 'tel' | 'url';
  required?: boolean;
  disabled?: boolean;
  error?: string;
  helperText?: string;
}

export interface TextProps {
  content: string;
  variant?: 'body' | 'heading' | 'caption' | 'label';
  size?: 'sm' | 'md' | 'lg' | 'xl';
  weight?: 'normal' | 'medium' | 'bold';
  color?: string;
}

export interface ImageProps {
  src: string;
  alt: string;
  width?: number | string;
  height?: number | string;
  fit?: 'cover' | 'contain' | 'fill' | 'none';
}

export interface ContainerProps {
  direction?: 'row' | 'column';
  gap?: number | string;
  padding?: number | string;
  align?: 'start' | 'center' | 'end' | 'stretch';
  justify?: 'start' | 'center' | 'end' | 'between' | 'around';
  wrap?: boolean;
}

export interface ListProps {
  items?: string[];
  ordered?: boolean;
  dividers?: boolean;
}

export interface SelectProps {
  label?: string;
  options: Array<{ value: string; label: string }>;
  value?: string;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
}

export interface CheckboxProps {
  label?: string;
  checked?: boolean;
  disabled?: boolean;
}

export interface SliderProps {
  label?: string;
  min?: number;
  max?: number;
  step?: number;
  value?: number;
  disabled?: boolean;
}

export interface DatePickerProps {
  label?: string;
  value?: string;
  min?: string;
  max?: string;
  required?: boolean;
  disabled?: boolean;
}

export interface ChipProps {
  label: string;
  variant?: 'filled' | 'outlined';
  selected?: boolean;
  deletable?: boolean;
  icon?: string;
}

export interface DividerProps {
  orientation?: 'horizontal' | 'vertical';
  inset?: boolean;
}

export interface ProgressProps {
  value?: number;
  variant?: 'linear' | 'circular';
  indeterminate?: boolean;
}

export interface IconProps {
  name: string;
  size?: number | string;
  color?: string;
}

/**
 * Map of built-in component types to their props
 */
export interface A2UIBuiltinComponents {
  card: CardProps;
  button: ButtonProps;
  'text-field': TextFieldProps;
  text: TextProps;
  image: ImageProps;
  container: ContainerProps;
  list: ListProps;
  select: SelectProps;
  checkbox: CheckboxProps;
  slider: SliderProps;
  'date-picker': DatePickerProps;
  chip: ChipProps;
  divider: DividerProps;
  progress: ProgressProps;
  icon: IconProps;
}

export type A2UIBuiltinComponentType = keyof A2UIBuiltinComponents;
