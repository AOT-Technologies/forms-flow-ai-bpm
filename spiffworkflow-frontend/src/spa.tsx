// src/spa.tsx

import React from 'react';
import ReactDOMClient from 'react-dom/client';
// @ts-expect-error
import singleSpaReact from 'single-spa-react';
import App from './App';
import AppSpa from './AppSpa';
import { cssLifecycleFactory } from 'vite-plugin-single-spa/ex';

// TODO: Check if needed. Added for SPA
import './index.scss';
import './index.css';

const lc = singleSpaReact({
    React,
    ReactDOMClient,
    rootComponent: AppSpa,
    errorBoundary(err: any, _info: any, _props: any) {
        return <div>Error: {err}</div>
    }
});

// IMPORTANT:  The argument passed here depends on the file name.
const cssLc = cssLifecycleFactory('spa');

export const bootstrap = [cssLc.bootstrap, lc.bootstrap];
export const mount = [cssLc.mount, lc.mount];
export const unmount = [cssLc.unmount, lc.unmount];
export const update = [lc.update];