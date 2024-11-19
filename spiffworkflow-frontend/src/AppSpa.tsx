import { defineAbility } from '@casl/ability';

import { createBrowserRouter, Outlet, RouterProvider } from 'react-router-dom';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AbilityContext } from './contexts/Can';
import APIErrorProvider from './contexts/APIErrorContext';
import ContainerForExtensionsMicro from './ContainerForExtensionsMicro';
import { BASENAME_URL } from './config';

const queryClient = new QueryClient();

export default function AppSpa() {
  const ability = defineAbility(() => {});
  const routeComponents = () => {
    return [
      {
        path: '*',
        element: <ContainerForExtensionsMicro />,
      },
    ];
  };

  /**
   * Note that QueryClientProvider and ReactQueryDevTools
   * are React Qery, now branded under the Tanstack packages.
   * https://tanstack.com/query/latest
   */
  const layout = () => {
    return (
      <div className="cds--white">
        <QueryClientProvider client={queryClient}>
          <APIErrorProvider>
            <AbilityContext.Provider value={ability}>
              <Outlet />
              <ReactQueryDevtools initialIsOpen={false} />
            </AbilityContext.Provider>
          </APIErrorProvider>
        </QueryClientProvider>
      </div>
    );
  };
  const router = createBrowserRouter([
    {
      path: '*',
      Component: layout,
      children: routeComponents(),
    },
  ],
  {
    basename: BASENAME_URL
  }
);
  return <RouterProvider router={router} />;
}
