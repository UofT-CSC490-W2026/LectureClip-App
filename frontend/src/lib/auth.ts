import {
  CognitoUser,
  CognitoUserAttribute,
  CognitoUserPool,
  CognitoUserSession,
  AuthenticationDetails,
} from 'amazon-cognito-identity-js'

const userPool = new CognitoUserPool({
  UserPoolId: import.meta.env.VITE_USER_POOL_ID as string,
  ClientId: import.meta.env.VITE_USER_POOL_CLIENT_ID as string,
})

export type AuthSession = {
  email: string
  idToken: string
}

export function signIn(email: string, password: string): Promise<AuthSession> {
  return new Promise((resolve, reject) => {
    const user = new CognitoUser({ Username: email, Pool: userPool })
    const details = new AuthenticationDetails({ Username: email, Password: password })
    user.authenticateUser(details, {
      onSuccess(session: CognitoUserSession) {
        resolve({ email, idToken: session.getIdToken().getJwtToken() })
      },
      onFailure: reject,
    })
  })
}

export function signUp(email: string, password: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const attributes = [new CognitoUserAttribute({ Name: 'email', Value: email })]
    userPool.signUp(email, password, attributes, [], (err) => {
      if (err) return reject(err)
      resolve()
    })
  })
}

export function confirmSignUp(email: string, code: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const user = new CognitoUser({ Username: email, Pool: userPool })
    user.confirmRegistration(code, true, (err) => {
      if (err) return reject(err)
      resolve()
    })
  })
}

export function signOut(): void {
  userPool.getCurrentUser()?.signOut()
}

export function getSession(): Promise<AuthSession | null> {
  return new Promise((resolve) => {
    const user = userPool.getCurrentUser()
    if (!user) return resolve(null)
    user.getSession((err: Error | null, session: CognitoUserSession | null) => {
      if (err || !session?.isValid()) return resolve(null)
      resolve({ email: user.getUsername(), idToken: session.getIdToken().getJwtToken() })
    })
  })
}