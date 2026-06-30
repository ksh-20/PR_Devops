import { Component, Input, Output, EventEmitter, HostListener, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';

export interface SelectOption {
  label: string;
  value: string;
}

@Component({
  selector: 'app-custom-select',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './custom-select.html',
  styleUrl: './custom-select.css'
})
export class CustomSelectComponent {
  /** Array of options — either plain strings or {label, value} objects */
  @Input() options: SelectOption[] | string[] = [];
  /** Currently selected value */
  @Input() value: string = '';
  /** Placeholder shown when nothing is selected */
  @Input() placeholder: string = 'Select…';
  /** Disabled state */
  @Input() disabled: boolean = false;

  @Output() valueChange = new EventEmitter<string>();

  isOpen = false;

  constructor(private el: ElementRef) {}

  get normalizedOptions(): SelectOption[] {
    return (this.options as any[]).map(o =>
      typeof o === 'string' ? { label: o, value: o } : o
    );
  }

  get selectedLabel(): string {
    if (!this.value) return this.placeholder;
    const opt = this.normalizedOptions.find(o => o.value === this.value);
    return opt ? opt.label : this.placeholder;
  }

  toggle(): void {
    if (this.disabled) return;
    this.isOpen = !this.isOpen;
  }

  select(opt: SelectOption): void {
    this.value = opt.value;
    this.valueChange.emit(opt.value);
    this.isOpen = false;
  }

  /** Close the dropdown when clicking outside */
  @HostListener('document:click', ['$event'])
  onDocumentClick(event: Event): void {
    if (!this.el.nativeElement.contains(event.target)) {
      this.isOpen = false;
    }
  }
}
