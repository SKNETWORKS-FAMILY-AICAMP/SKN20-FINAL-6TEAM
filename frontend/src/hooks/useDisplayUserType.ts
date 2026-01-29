import { useAuthStore } from '../stores/authStore';
import type { User } from '../types';

type UserTypeCode = User['type_code'];

const DEFAULT_USER_TYPE: UserTypeCode = 'U002';

/**
 * Returns the display user type code.
 * - Unauthenticated or pre-startup users -> U002
 * - Admin -> U001
 * - Otherwise -> user's actual type_code
 */
export const useDisplayUserType = (): UserTypeCode => {
  const { isAuthenticated, user } = useAuthStore();

  if (!isAuthenticated || !user) {
    return DEFAULT_USER_TYPE;
  }

  return user.type_code;
};
