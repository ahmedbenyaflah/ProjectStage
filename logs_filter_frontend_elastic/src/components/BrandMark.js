import React from 'react';

/** Orange logo from `public/orange.svg` */
export default function BrandMark({ className = 'h-10 w-10 shrink-0', alt = 'Orange' }) {
  return (
    <img
      src={`${process.env.PUBLIC_URL}/orange.svg`}
      alt={alt}
      className={`object-contain ${className}`}
      width={50}
      height={50}
      decoding="async"
    />
  );
}
